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

import json
import math
import os
import random
import sys
import time
from collections import deque

import pygame


def _asset_path(*parts):
    """Résout un asset : essaie <base>/… puis <racine>/… (les assets sont parfois
    à la racine du repo et pas dans src/). Renvoie le 1er chemin qui existe."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(base, *parts)
    if os.path.exists(cand):
        return cand
    alt = os.path.join(os.path.dirname(base), *parts)
    return alt if os.path.exists(alt) else cand


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

WIDTH, HEIGHT   = 1280, 720
DISPLAY_W, DISPLAY_H = WIDTH, HEIGHT
SCALE_X = 1.0
SCALE_Y = 1.0
FPS = 60

# ── Sprite Frounette — bornes mesurées en pixels source (frame 100×100) ──────
# walk union : x=41..57 (w=17), y=38..59 (h=22)
SPR_SCALE       = 2.6     # ×2.6 (légèrement réduit)
SPR_CHAR_X0     = 41      # bord gauche du perso dans frame src
SPR_CHAR_Y0     = 38      # bord haut (tête) dans frame src
SPR_CHAR_W      = 17      # largeur perso en pixels src
# Les pixels y=55-59 sont l'ombre intégrée au sprite (couleur 83,69,69).
# Les vraies bottes finissent à y=54. On ancre là pour que les pieds touchent le sol.
# L'ombre intégrée (15 px écran) se dépose naturellement sur la plateforme.
SPR_CHAR_FEET_Y = 54      # y bas des bottes (sans l'ombre built-in du sprite)
SPR_CHAR_H      = SPR_CHAR_FEET_Y - SPR_CHAR_Y0 + 1    # 17 px — hauteur corps seul
# Hitbox = corps visible (bottes incluses, ombre exclue)
PLAYER_W = SPR_CHAR_W * SPR_SCALE                        # 51
PLAYER_H = SPR_CHAR_H * SPR_SCALE                        # 51
# Offsets de blit (ancre = bas du pixel pied → bas du bloc 3×3 = +1 src px)
SPR_BLIT_OX       = SPR_CHAR_X0 * SPR_SCALE             # 123 — bord gauche
SPR_BLIT_FEET_OY  = (SPR_CHAR_FEET_Y + 1) * SPR_SCALE   # 165 — bas du bloc pied

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


class _FrozenKeys:
    """État clavier neutre : tout est relâché (héros gelé pendant une cinématique)."""
    def __getitem__(self, k):
        return False
_FROZEN_KEYS = _FrozenKeys()

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
    TELEGRAPH  = (80, 160, 255)
    TELEGRAPH_S = (60, 130, 255)  # plus saturé pour les gros tells
    TELEGRAPH_DREAM = (255, 100, 200)
    TELEGRAPH_ANY   = (255, 185, 45)


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


def _strip_black_bg(surf, thresh=12):
    """Rend transparent le fond noir d'un sprite (supprime le carré).
    Met alpha=0 pour tout pixel dont max(r,g,b) < thresh. Utilise surfarray
    (numpy) si dispo, sinon retourne la surface inchangée."""
    try:
        import numpy as _np
        surf = surf.convert_alpha()
        rgb = pygame.surfarray.pixels3d(surf)        # (w,h,3) vue
        alpha = pygame.surfarray.pixels_alpha(surf)  # (w,h)   vue
        maxc = rgb.max(axis=2)
        # Fondu doux : alpha proportionnel à la luminance près du seuil,
        # coupe nette en dessous → plus de halo noir résiduel.
        mask = maxc < thresh
        alpha[mask] = 0
        del rgb, alpha   # libère les locks surfarray
        return surf
    except Exception as e:
        print(f"[STRIP] fond non retiré: {e}")
        return surf


def _recolor_gradient(surf, lo, hi):
    """Recolorise un sprite selon sa luminance : ombres→lo, lumières→hi.
    Conserve tout le détail (au lieu d'aplatir en une couleur unie).
    Préserve l'alpha. Retourne une nouvelle surface."""
    try:
        import numpy as _np
        src = surf.convert_alpha()
        rgb = pygame.surfarray.array3d(src).astype(_np.float32)   # (w,h,3)
        alpha = pygame.surfarray.array_alpha(src)                 # (w,h)
        lum = (0.30 * rgb[..., 0] + 0.59 * rgb[..., 1] +
               0.11 * rgb[..., 2]) / 255.0                        # 0..1
        lum = _np.clip(lum * 1.15, 0.0, 1.0)[..., None]           # léger boost
        lo_a = _np.array(lo, dtype=_np.float32)
        hi_a = _np.array(hi, dtype=_np.float32)
        out = lo_a + (hi_a - lo_a) * lum                          # (w,h,3)
        res = pygame.Surface(src.get_size(), pygame.SRCALPHA)
        pygame.surfarray.blit_array(res, out.astype(_np.uint8))
        a_view = pygame.surfarray.pixels_alpha(res)
        a_view[:] = alpha
        del a_view
        return res
    except Exception as e:
        print(f"[RECOLOR] échec: {e}")
        return surf


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
    _sprite = None   # classe : chargé une fois, réutilisé

    def __init__(self, x, y, vx, vy, dmg=1, dim=DIM_REAL):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.dmg = dmg
        self.dim = dim
        self.life = ARROW_LIFETIME
        # Chargement unique de l'asset flèche
        if Arrow._sprite is None:
            try:
                _base = getattr(sys, '_MEIPASS',
                                os.path.dirname(os.path.abspath(__file__)))
                _raw = pygame.image.load(
                    os.path.join(_base, "assets", "images", "arrow.png")
                ).convert_alpha()
                Arrow._sprite = pygame.transform.scale(_raw, (48, 48))
            except Exception:
                Arrow._sprite = False   # sentinel : ne plus retenter
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
        if Arrow._sprite:
            # Rotation du sprite selon la direction de vol
            ang_deg = -math.degrees(ang)
            rotated = pygame.transform.rotate(Arrow._sprite, ang_deg)
            r = rotated.get_rect(center=(int(cx), int(cy)))
            surf.blit(rotated, r)
        else:
            # Fallback procédural si asset absent
            if self.dmg >= 3:   col = Pal.ARROW_CH2
            elif self.dmg >= 2: col = Pal.ARROW_CH1
            else: col = Pal.ARROW
            length = 12 + self.dmg * 4
            x2 = cx - math.cos(ang) * length
            y2 = cy - math.sin(ang) * length
            pygame.draw.line(surf, col, (cx, cy), (x2, y2), 2 + self.dmg)
            pygame.draw.circle(surf, col, (int(cx), int(cy)), 2 + self.dmg)


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
    # Gradient mauve/violet : bord foncé → violet → blanc au centre (défaut)
    _LAYERS = [
        (1.00, (25,  5,  55)),   # violet très foncé — bords extérieurs
        (0.72, (80, 20, 150)),   # violet foncé
        (0.48, (150, 60, 230)),  # mauve normal
        (0.28, (210, 150, 255)), # mauve clair
        (0.12, (238, 220, 255)), # quasi blanc mauve
        (0.04, (250, 245, 255)), # blanc pur au cœur
    ]
    # Gradient sang-de-lune : phase 5 — même structure que le mauve mais cramoisi
    _LAYERS_RED = [
        (1.00, (28,  0,  12)),   # rouge-violet très sombre — bords
        (0.72, (100,  5,  35)),  # cramoisi profond
        (0.48, (195, 18,  60)),  # rouge sang
        (0.28, (235, 70,  90)),  # rouge clair / rose sombre
        (0.12, (255, 190, 200)), # quasi-blanc rosé
        (0.04, (255, 245, 248)), # blanc pur au cœur
    ]

    def __init__(self, rect, dim, life=24, color=None, dmg=1, hits_any_dim=False, red=False, once=False):
        self.rect = rect
        self.dim = dim
        self.life = life
        self.max_life = life
        self.color = color or Pal.BEAM_FILL  # conservé pour compatibilité
        self.dmg = dmg
        self.hits_any_dim = hits_any_dim
        self.red = red
        self.once = once
        self._hit_done = False
        self.dead = False

    def update(self):
        self.life -= 1
        if self.life <= 0: self.dead = True

    def draw(self, surf, cam):
        t = max(0.0, self.life / self.max_life)
        if t <= 0:
            return
        sx = self.rect.x - cam[0]
        sy = self.rect.y - cam[1]
        vertical = self.rect.h > self.rect.w

        s = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        frac_life = t
        layers = self._LAYERS_RED if self.red else self._LAYERS
        if vertical:
            cx = self.rect.w // 2
            for frac, col in layers:
                lw = max(1, int(self.rect.w * frac))
                a  = int(220 * t)
                pygame.draw.rect(s, (*col, a),
                                 (cx - lw // 2, 0, lw, self.rect.h))
            # Ligne centrale vive
            center_x_in_s = s.get_width() // 2
            line_a = int(180 * frac_life)
            pygame.draw.line(s, (255, 252, 248, line_a), (center_x_in_s, 0), (center_x_in_s, s.get_height()))
        else:
            cy = self.rect.h // 2
            for frac, col in layers:
                lh = max(1, int(self.rect.h * frac))
                a  = int(220 * t)
                pygame.draw.rect(s, (*col, a),
                                 (0, cy - lh // 2, self.rect.w, lh))
            center_y_in_s = s.get_height() // 2
            line_a = int(180 * frac_life)
            pygame.draw.line(s, (255, 252, 248, line_a), (0, center_y_in_s), (s.get_width(), center_y_in_s))

        surf.blit(s, (sx, sy))


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
        if color is not None:
            self.color = color
        elif params.get('hits_any_dim', False):
            self.color = Pal.TELEGRAPH_ANY
        elif dim == DIM_DREAM:
            self.color = Pal.TELEGRAPH_DREAM
        else:
            self.color = Pal.TELEGRAPH
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
        t2 = t * t           # courbe quadratique : buildup lent puis brutal
        pulse = 0.7 + 0.3 * math.sin(self.timer * 0.35)

        if self.kind == "beam_v":
            x    = self.params["x"] - cam[0]
            top  = self.params.get("top", -200) - cam[1]
            bot  = self.params.get("bottom", HEIGHT + 200) - cam[1]
            fw   = self.params.get("final_width", 50)
            h    = max(1, int(bot - top))
            pad  = 50   # espace pour le glow extérieur

            s = pygame.Surface((fw + pad * 2, h), pygame.SRCALPHA)
            cx = pad   # x du bord gauche du rect dans la surface

            # Glow extérieur multicouche — s'intensifie avec t²
            for extra, base_a in [(pad, 10), (pad * 2 // 3, 20), (pad // 2, 35), (pad // 4, 55)]:
                ga = int(base_a * t2 * pulse)
                pygame.draw.rect(s, (*self.color, ga),
                                 (cx - extra, 0, fw + extra * 2, h))

            # Rectangle principal — monte de presque transparent à semi-translucide
            main_a = int(15 + 90 * t2 * pulse)
            pygame.draw.rect(s, (*self.color, main_a), (cx, 0, fw, h))

            # Bords nets du rectangle
            border_a = int(70 + 90 * t)
            pygame.draw.rect(s, (*self.color, border_a), (cx, 0, fw, h), 2)

            surf.blit(s, (int(x - fw / 2 - pad), int(top)))

        elif self.kind == "beam_h":
            y     = self.params["y"] - cam[1]
            left  = self.params.get("left", -200) - cam[0]
            right = self.params.get("right", WIDTH + 200) - cam[0]
            fh    = self.params.get("final_height", 50)
            w     = max(1, int(right - left))
            pad   = 50

            s = pygame.Surface((w, fh + pad * 2), pygame.SRCALPHA)
            cy = pad

            for extra, base_a in [(pad, 10), (pad * 2 // 3, 20), (pad // 2, 35), (pad // 4, 55)]:
                ga = int(base_a * t2 * pulse)
                pygame.draw.rect(s, (*self.color, ga),
                                 (0, cy - extra, w, fh + extra * 2))

            main_a = int(15 + 90 * t2 * pulse)
            pygame.draw.rect(s, (*self.color, main_a), (0, cy, w, fh))

            border_a = int(70 + 90 * t)
            pygame.draw.rect(s, (*self.color, border_a), (0, cy, w, fh), 2)

            surf.blit(s, (int(left), int(y - fh / 2 - pad)))
        elif self.kind == "circle":
            # Verrou de visée lisible : zone mortelle nette + anneau qui converge
            # + croix tournante + flash blanc juste avant le tir.
            x = int(self.params["x"] - cam[0])
            y = int(self.params["y"] - cam[1])
            r = int(self.params.get("r", 50))
            pad = 16
            s = pygame.Surface((r * 2 + pad * 2, r * 2 + pad * 2), pygame.SRCALPHA)
            cc = r + pad
            # remplissage qui monte (danger imminent)
            pygame.draw.circle(s, (*self.color, int(28 + 95 * t2)), (cc, cc), r)
            # bord net de la zone mortelle
            pygame.draw.circle(s, (*self.color, int(110 + 120 * t)), (cc, cc), r, 3)
            # anneau extérieur qui se resserre vers le bord : « ça arrive »
            conv = int(r + (pad + 26) * (1.0 - t))
            pygame.draw.circle(s, (*self.color, int(80 + 120 * t)), (cc, cc),
                               max(r + 1, conv), 2)
            # croix de visée tournante
            ang = self.timer * 0.12
            for kk in range(4):
                aa = ang + kk * math.pi / 2
                x1 = cc + int(math.cos(aa) * (r * 0.32))
                y1 = cc + int(math.sin(aa) * (r * 0.32))
                x2 = cc + int(math.cos(aa) * (r * 0.92))
                y2 = cc + int(math.sin(aa) * (r * 0.92))
                pygame.draw.line(s, (*self.color, int(120 + 120 * t)),
                                 (x1, y1), (x2, y2), 2)
            # snap final : éclat blanc juste avant le tir
            if t > 0.82:
                fa = int(210 * (t - 0.82) / 0.18)
                pygame.draw.circle(s, (255, 255, 255, fa), (cc, cc), r, 4)
            surf.blit(s, (x - cc, y - cc))
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
            pad = 6
            s = pygame.Surface((r * 2 + pad * 2, r * 2 + pad * 2), pygame.SRCALPHA)
            cc = r + pad
            pygame.draw.circle(s, (*self.color, a), (cc, cc), r, 3)
            # liseré intérieur léger pour lire le rayon final qui se remplit
            pygame.draw.circle(s, (*self.color, int(a * 0.4)), (cc, cc), max(1, r - 5), 1)
            # snap final : éclat blanc juste avant la déflagration
            if t > 0.85:
                fa = int(210 * (t - 0.85) / 0.15)
                pygame.draw.circle(s, (255, 255, 255, fa), (cc, cc), r, 4)
            surf.blit(s, (x - cc, y - cc))
        elif self.kind == "collapse":
            # SUPERNOVA — effondrement : un anneau SE RESSERRE vers un cœur qui
            # s'embrase, dards rentrants → lecture inverse du « ring » : ça aspire
            # tout, puis ça DÉTONE. Le joueur lit le compte à rebours de l'implosion.
            x = int(self.params["x"] - cam[0])
            y = int(self.params["y"] - cam[1])
            R = int(self.params.get("r", 300))
            pad = 12
            s = pygame.Surface((R * 2 + pad * 2, R * 2 + pad * 2), pygame.SRCALPHA)
            cc = R + pad
            # cœur de l'étoile qui charge (croît avec t²)
            core = int(6 + 34 * t2)
            pygame.draw.circle(s, (*self.color, int(55 + 150 * t2)), (cc, cc), core)
            pygame.draw.circle(s, (255, 255, 255, int(130 * t2)), (cc, cc), max(1, core // 2))
            # anneau qui converge vers le cœur (de R → ~0.18R)
            rr = max(2, int(R * (1.0 - 0.82 * t)))
            pygame.draw.circle(s, (*self.color, int(90 + 150 * t)), (cc, cc), rr, 3)
            pygame.draw.circle(s, (*self.color, int(40 + 80 * t)),
                               (cc, cc), max(2, rr - 5), 1)
            # dards rentrants qui pointent vers le cœur (aspiration)
            for kk in range(14):
                aa = kk * math.tau / 14 + self.timer * 0.04
                ln = 14 + 22 * (1.0 - t)
                x1 = cc + int(math.cos(aa) * (rr + 6))
                y1 = cc + int(math.sin(aa) * (rr + 6))
                x2 = cc + int(math.cos(aa) * (rr + 6 + ln))
                y2 = cc + int(math.sin(aa) * (rr + 6 + ln))
                pygame.draw.line(s, (*self.color, int(70 + 140 * t)), (x1, y1), (x2, y2), 2)
            # snap blanc final : la détonation est imminente
            if t > 0.8:
                fa = int(235 * (t - 0.8) / 0.2)
                pygame.draw.circle(s, (255, 255, 255, fa), (cc, cc), core + 8, 3)
            surf.blit(s, (x - cc, y - cc))
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
# Hazards signature d'Aegis : laser rotatif & invocations du Vide
# ---------------------------------------------------------------------------

class RotLaser:
    """Rayon mortel rotatif ancré sur Aegis — les « aiguilles d'horloge ».
    Pendant `warmup` il n'est qu'un fin trait d'alerte (non létal) ; ensuite il
    devient un faisceau épais et létal qui balaie l'arène. Le test de collision
    est un vrai point-vers-segment (pas une AABB)."""
    def __init__(self, boss, angle, omega, length=1700, width=46, dmg=3,
                 life=300, warmup=46, color=(235, 40, 165)):
        self.boss = boss
        self.angle = angle
        self.omega = omega
        self.length = length
        self.width = width
        self.dmg = dmg
        self.life = life
        self.max_life = max(1, life)
        self.warmup = warmup
        self.max_warmup = max(1, warmup)
        self.color = color
        self.dead = False
        self.went_live = False

    @property
    def live(self):
        return self.warmup <= 0

    def _origin(self):
        return (self.boss.x, self.boss.y + self.boss.float_offset)

    def update(self):
        self.angle += self.omega
        if self.warmup > 0:
            self.warmup -= 1
            return
        self.life -= 1
        if self.life <= 0:
            self.dead = True

    def hits(self, target_rect):
        if not self.live:
            return False
        ox, oy = self._origin()
        cx, cy = target_rect.center
        dx, dy = math.cos(self.angle), math.sin(self.angle)
        proj = (cx - ox) * dx + (cy - oy) * dy
        if proj < 0 or proj > self.length:
            return False
        px = ox + dx * proj; py = oy + dy * proj
        # collision un peu plus étroite que le halo dessiné : on peut frôler le bord
        return math.hypot(cx - px, cy - py) < self.width * 0.42

    def draw(self, surf, cam):
        ox, oy = self._origin()
        ox -= cam[0]; oy -= cam[1]
        dx, dy = math.cos(self.angle), math.sin(self.angle)
        ex = ox + dx * self.length
        ey = oy + dy * self.length
        ws = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        if not self.live:
            # ── Télégraphe : trait fin qui s'épaissit et pulse ──
            t = 1.0 - self.warmup / self.max_warmup
            a = int(60 + 130 * t)
            w = max(1, int(2 + 5 * t))
            pygame.draw.line(ws, (*self.color, a), (int(ox), int(oy)),
                             (int(ex), int(ey)), w)
            pygame.draw.line(ws, (255, 250, 255, int(90 * t)),
                             (int(ox), int(oy)), (int(ex), int(ey)), max(1, w // 2))
        else:
            # ── Faisceau létal : halo large multicouche + cœur blanc ──
            fade = max(0.30, min(1.0, self.life / 16.0))
            px, py = -dy, dx
            # le bord externe (frac 1.0) couvre la zone létale → assez visible
            for frac, alpha in ((1.0, 90), (0.62, 150), (0.32, 210)):
                hw = self.width * 0.5 * frac
                poly = [(ox + px * hw, oy + py * hw),
                        (ex + px * hw, ey + py * hw),
                        (ex - px * hw, ey - py * hw),
                        (ox - px * hw, oy - py * hw)]
                pygame.draw.polygon(ws, (*self.color, int(alpha * fade)), poly)
            pygame.draw.line(ws, (255, 250, 255, int(235 * fade)),
                             (int(ox), int(oy)), (int(ex), int(ey)),
                             max(2, int(self.width * 0.13)))
        surf.blit(ws, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


class VoidSpawn:
    """Petit « œil » du Vide en orbite autour d'Aegis. Tire périodiquement un
    orbe à tête chercheuse vers le joueur tant qu'il vit."""
    def __init__(self, boss, angle, orbit, life=480, color=(255, 95, 215)):
        self.boss = boss
        self.angle = angle
        self.orbit = orbit
        self.omega = random.uniform(0.018, 0.032) * random.choice((-1, 1))
        self.life = life
        self.color = color
        self.fire_t = random.randint(45, 85)
        self.spawn_t = 0
        self.x = boss.x; self.y = boss.y
        self.r = 18
        self.dead = False

    def update(self, player, projectiles, particles):
        self.spawn_t += 1
        self.angle += self.omega
        bob = math.sin(self.spawn_t * 0.06) * 14
        rad = self.orbit + bob
        self.x = self.boss.x + math.cos(self.angle) * rad
        self.y = self.boss.y + self.boss.float_offset + math.sin(self.angle) * rad
        self.life -= 1
        if self.life <= 0:
            self.dead = True
            burst(particles, self.x, self.y, 16, self.color, 4.0, 26, 0.0, 3)
            return
        if self.spawn_t < 26:        # apparition : pas encore de tir
            return
        self.fire_t -= 1
        if self.fire_t <= 0:
            self.fire_t = random.randint(75, 120)
            ang = math.atan2(player.rect.centery - self.y,
                             player.rect.centerx - self.x)
            projectiles.append(BossProjectile(
                self.x, self.y, math.cos(ang) * 3.0, math.sin(ang) * 3.0, DIM_REAL,
                radius=8, life=300, homing=0.05, target=player, color=self.color,
                kind="orb", dmg=2, hits_any_dim=True))
            burst(particles, self.x, self.y, 6, self.color, 3.0, 16, 0.0, 2)

    def draw(self, surf, cam):
        cx = int(self.x - cam[0]); cy = int(self.y - cam[1])
        grow = min(1.0, self.spawn_t / 26.0)
        r = max(2, int(self.r * grow))
        gs = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*self.color, 70), (r * 2, r * 2), r * 2)
        pygame.draw.circle(gs, (*self.color, 120), (r * 2, r * 2), int(r * 1.3))
        surf.blit(gs, (cx - r * 2, cy - r * 2), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(surf, (20, 4, 28), (cx, cy), r)              # corps sombre
        pygame.draw.circle(surf, self.color, (cx, cy), max(1, r // 2))  # pupille
        pygame.draw.circle(surf, self.color, (cx, cy), r, 2)            # liseré


class CorrosionPool:
    """Mare de corrosion du Vide : une flaque acide qui ronge le sol. Tant que
    le joueur la touche, elle ronge sa vie par paliers rapides. Elle jaillit,
    bouillonne, vomit des vapeurs, puis se résorbe. Signature d'Aegis :
    interdire le terrain — un dieu qui souille le monde sous tes pieds."""
    def __init__(self, x, y, r=84, life=360, dmg=1, color=(235, 40, 165)):
        self.x = float(x); self.y = float(y)
        self.r = r
        self.life = life
        self.max_life = life
        self.dmg = dmg
        self.color = color
        self.dead = False
        self.t = 0
        self.bubbles = [(random.uniform(-0.8, 0.8), random.uniform(0.3, 1.0),
                         random.uniform(0, math.tau)) for _ in range(7)]

    @property
    def cur_r(self):
        f = self.life / self.max_life
        if f > 0.88:                       # apparition (jaillit violemment)
            return self.r * max(0.0, 1.0 - (f - 0.88) / 0.12)
        if f < 0.18:                       # résorption
            return self.r * (f / 0.18)
        return float(self.r)

    @property
    def lethal(self):
        # Mortelle seulement une fois bien sortie (lisibilité : on voit venir).
        return self.cur_r > self.r * 0.5

    @property
    def rect(self):
        r = int(self.cur_r)
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def update(self, player, particles):
        self.t += 1
        self.life -= 1
        if self.life <= 0:
            self.dead = True
            return
        r = self.cur_r
        if r > 6:
            px = player.rect.centerx
            py = player.rect.bottom
            if self.lethal and abs(px - self.x) < r and abs(py - self.y) < r * 0.85:
                if self.t % 13 == 0:        # rongement RAPIDE (était 18)
                    player.hurt(self.dmg)
                    if particles is not None:
                        burst(particles, px, py, 6, self.color, 3.2, 18, 0.0, 3)
            if particles is not None and self.t % 3 == 0:
                # vapeurs acides qui montent (menace lisible)
                burst(particles, self.x + random.uniform(-r, r), self.y, 1,
                      self.color, 1.8, 26, -0.08, 3)

    def draw(self, surf, cam):
        r = int(self.cur_r)
        if r <= 2:
            return
        cx = int(self.x - cam[0]); cy = int(self.y - cam[1])
        pulse = 0.6 + 0.4 * math.sin(self.t * 0.22)
        danger = self.lethal
        pad = 14
        s = pygame.Surface((r * 2 + pad * 2, r + pad * 2), pygame.SRCALPHA)
        ox, oy = pad, pad
        # 1) halo de danger (lueur rouge-rose pulsante qui crie « ne touche pas »)
        glow_a = int((55 + 65 * pulse) * (1.0 if danger else 0.4))
        pygame.draw.ellipse(s, (255, 60, 120, glow_a),
                            (ox - 8, oy - 5, r * 2 + 16, r + 10))
        # 2) nappe acide
        pygame.draw.ellipse(s, (*self.color, int(95 * pulse)), (ox, oy, r * 2, r))
        # 3) cœur du vide (creux sombre — contraste fort)
        pygame.draw.ellipse(s, (40, 4, 52, 200),
                            (ox + r // 3, oy + r // 4, r * 2 - r * 2 // 3, r - r // 2))
        # 4) bord net mortel (lisibilité : la limite du danger)
        pygame.draw.ellipse(s, (*self.color, 230), (ox, oy, r * 2, r), 3)
        # 5) bulles qui crèvent en surface
        for bx, by, ph in self.bubbles:
            phase = (self.t * 0.05 + ph) % 1.0
            bxp = ox + r + int(bx * r * 0.85)
            byp = oy + int(r * (0.5 - 0.4 * math.sin(phase * math.pi)))
            br = 2 + int(3 * math.sin(phase * math.pi))
            if br > 0:
                pygame.draw.circle(s, (*self.color, int(180 * pulse)), (bxp, byp), br)
        surf.blit(s, (cx - r - pad, cy - oy),
                  special_flags=pygame.BLEND_RGBA_ADD)


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
# Orbe de soin (récompense fin de phase 4)
# ---------------------------------------------------------------------------

class HealOrb:
    def __init__(self, x, y, amount=5):
        self.x = float(x)
        self.y = float(y)
        self.amount = amount
        self.radius = 14
        self.t = 0.0
        self.collected = False

    def update(self):
        self.t += 0.07

    def draw(self, surf, cam):
        cx = int(self.x - cam[0])
        cy = int(self.y - cam[1]) + int(math.sin(self.t) * 8)
        # Glow extérieur pulsant
        pulse = 0.6 + 0.4 * math.sin(self.t * 1.4)
        glow_r = int(self.radius * 2.4)
        gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (60, 220, 100, int(55 * pulse)), (glow_r, glow_r), glow_r)
        surf.blit(gs, (cx - glow_r, cy - glow_r))
        # Corps de l'orbe
        pygame.draw.circle(surf, (30, 180, 70), (cx, cy), self.radius)
        pygame.draw.circle(surf, (120, 255, 150), (cx, cy), self.radius, 2)
        # Croix de soin
        pygame.draw.rect(surf, (200, 255, 210), (cx - 2, cy - 7, 4, 14))
        pygame.draw.rect(surf, (200, 255, 210), (cx - 7, cy - 2, 14, 4))
        # Reflet
        pygame.draw.circle(surf, (200, 255, 220), (cx - 4, cy - 4), 3)

    def collect_rect(self):
        return pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius,
                           self.radius * 2, self.radius * 2)


# ---------------------------------------------------------------------------
# Joueur
# ---------------------------------------------------------------------------

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_W, PLAYER_H)  # 68×88 — hitbox = contenu sprite
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
        self.shield = 0  # bouclier (excédant de soin)

        self.dimension = DIM_REAL
        self.can_swap = True   # la « Fissure » (switch de dim) : Lune oui, Aegis non

        self.bow_cd = 0   # cooldown unique, plus de charge
        self._aim_angle = 0.0   # angle vers le curseur (radians, mis à jour chaque frame)

        self.score = 0
        self.spawn = (x, y)
        self.frame = 0

        # Sons
        _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        try:
            self._snd_jump = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "jump.mp3"))
            self._snd_jump.set_volume(0.15)
        except Exception:
            self._snd_jump = None
        try:
            self._snd_swap = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "swap.mp3"))
            self._snd_swap.set_volume(0.15)
        except Exception:
            self._snd_swap = None

        # ── Sprites de Frounette ─────────────────────────────────────────
        _SPR_SCALE = SPR_SCALE  # ×3 → frames 300×300 (personnage 51×66 visible)

        def _load_sheet(name, fw=100, fh=100):
            """Découpe un spritesheet, redimensionne chaque frame à fw*scale × fh*scale."""
            try:
                # Cherche dans <base>/assets ET dans <base>/../assets (selon qu'on
                # lance depuis src/ ou la racine) : les assets sont parfois à la racine.
                path = os.path.join(_base, "assets", "images", name)
                if not os.path.exists(path):
                    alt = os.path.join(os.path.dirname(_base), "assets", "images", name)
                    if os.path.exists(alt):
                        path = alt
                sheet = pygame.image.load(path).convert_alpha()
                cols = sheet.get_width() // fw
                nw   = int(fw * _SPR_SCALE)
                nh   = int(fh * _SPR_SCALE)
                frames = []
                for c in range(cols):
                    raw = sheet.subsurface(pygame.Rect(c * fw, 0, fw, fh))
                    frames.append(pygame.transform.scale(raw, (nw, nh)))
                return frames
            except Exception:
                return []

        self._spr_walk   = _load_sheet("frounette_walk.png")    # 8 frames  → 200×200
        self._spr_attack = _load_sheet("frounette_attack.png")  # 9 frames  → 200×200
        self._spr_hurt   = _load_sheet("frounette_hurt.png")    # 4 frames  → 200×200
        self._spr_death  = _load_sheet("frounette_death.png")   # 4 frames  → 200×200

        # Machine à états d'animation
        self._anim_state  = 'idle'   # 'idle' | 'walk' | 'attack' | 'hurt' | 'death'
        self._anim_t      = 0        # compteur de frames dans l'état courant

        # ── Forme du NÉANT (transformation de la finale) ─────────────────
        self._void_form  = False     # True → on dessine le « Destructeur du Vide »
        self._void_u     = 0.0       # 0→1 : avancée de la transformation
        self._spr_void   = None      # frames néant (construites à la volée)
        self._void_head  = (0, 0)    # ancre des yeux (coord. dans le frame)

    def center(self):
        return self.rect.center

    def respawn(self):
        self.rect.topleft = self.spawn
        self.vx = 0; self.vy = 0
        self.hp = self.max_hp
        self.shield = 0
        self.dimension = DIM_REAL
        self.dash_timer = 0; self.dash_cooldown = 0
        self.swap_cooldown = 0; self.swap_invuln = 0; self.invuln = 0
        self.jumps_used = 0
        self.jump_history.clear()
        self._anim_state = 'idle'
        self._anim_t     = 0

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
            if self._snd_jump: self._snd_jump.play()
            burst(particles, self.rect.centerx, self.rect.bottom, 8,
                  pal_part(self.dimension), 3.0, 18, 0.2, 3)
            return "JUMP"

        if self.jumps_used < self.max_jumps:
            self.vy = JUMP_FORCE * 0.92
            self.jumps_used += 1
            if self._snd_jump: self._snd_jump.play()
            burst(particles, self.rect.centerx, self.rect.bottom, 12,
                  pal_part(self.dimension), 4.0, 22, 0.1, 3)
            return "DOUBLE"

        if len(self.jump_history) >= 3 and self.swap_cooldown <= 0 and self.can_swap:
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
        # Animation d'attaque
        if self._anim_state not in ('death', 'hurt'):
            self._anim_state = 'attack'
            self._anim_t = 0
        return Arrow(cx, cy, vx, vy, dmg=BOW_DAMAGE, dim=self.dimension)

    def swap_dimension(self, particles):
        self.dimension = DIM_DREAM if self.dimension == DIM_REAL else DIM_REAL
        self.swap_cooldown = SWAP_COOLDOWN
        self.swap_invuln = SWAP_INVULN_FRAMES
        self.invuln = max(self.invuln, SWAP_INVULN_FRAMES)
        self.dream_stay_t = 0   # reset chrono à chaque switch
        if self._snd_swap: self._snd_swap.play()
        cx, cy = self.rect.center
        burst(particles, cx, cy, 50, pal_part(self.dimension), 9.0, 45, 0.0, 5)
        burst(particles, cx, cy, 24, pal_accent(self.dimension), 6.0, 30, 0.0, 4)

    def hurt(self, dmg=1):
        if self.invuln > 0: return False
        if self.shield > 0:
            absorbed = min(self.shield, dmg)
            self.shield -= absorbed
            dmg -= absorbed
        self.hp -= dmg
        self.invuln = INVULN_FRAMES
        # Animation de dégâts (si pas déjà en mort)
        if self._anim_state != 'death':
            self._anim_state = 'hurt'
            self._anim_t = 0
        return True

    def heal(self, amount):
        """Soigne amount HP. L'excédant se convertit en shield."""
        needed = self.max_hp - self.hp
        healed = min(amount, needed)
        self.hp += healed
        overflow = amount - healed
        if overflow > 0:
            self.shield = min(self.shield + overflow, 10)

    def _get_anim_frame(self):
        """Retourne la surface sprite courante (ou None si assets absents)."""
        SPD = {'idle': 8, 'walk': 6, 'attack': 5, 'hurt': 6, 'death': 9}
        SHEETS = {
            'idle':   self._spr_walk,
            'walk':   self._spr_walk,
            'attack': self._spr_attack,
            'hurt':   self._spr_hurt,
            'death':  self._spr_death,
        }
        state = self._anim_state
        sheet = SHEETS.get(state, [])
        if not sheet:
            return None
        spd   = SPD.get(state, 6)
        n     = len(sheet)
        idx   = self._anim_t // spd

        # Animations one-shot (attack, hurt, death)
        if state in ('attack', 'hurt'):
            idx = min(idx, n - 1)
            if self._anim_t >= spd * n:
                # Animation terminée → retour idle/walk
                self._anim_state = 'idle'
                self._anim_t     = 0
                idx = 0
        elif state == 'death':
            idx = min(idx, n - 1)   # geler sur la dernière frame
        else:
            idx = idx % n           # boucle walk/idle

        frame = sheet[idx]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        return frame

    def _voidify(self, frame):
        """Transforme un frame du héros en silhouette du NÉANT : corps sombre
        criblé d'étoiles + liseré glacial (un « Destructeur » fait de vide)."""
        try:
            mask = pygame.mask.from_surface(frame)
        except Exception:
            return frame
        w, h = frame.get_size()
        body = mask.to_surface(setcolor=(11, 8, 26, 255), unsetcolor=(0, 0, 0, 0))
        bb = frame.get_bounding_rect()
        st = random.Random(1234)
        for _ in range(90):                       # champ d'étoiles clippé à la silhouette
            sx = st.randint(bb.left, max(bb.left, bb.right - 1))
            sy = st.randint(bb.top, max(bb.top, bb.bottom - 1))
            if 0 <= sx < w and 0 <= sy < h and mask.get_at((sx, sy)):
                c = st.choice(((215, 228, 255), (150, 195, 255), (255, 255, 255), (190, 150, 255)))
                body.set_at((sx, sy), c)
        edge = mask.to_surface(setcolor=(182, 226, 255, 220), unsetcolor=(0, 0, 0, 0))
        glow = mask.to_surface(setcolor=(120, 190, 255, 85), unsetcolor=(0, 0, 0, 0))
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, -3), (-3, 3), (3, 3)):
            out.blit(glow, (dx, dy))              # halo extérieur doux
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
            out.blit(edge, (dx, dy))              # liseré glacial net
        out.blit(body, (0, 0))
        return out

    def _build_void(self):
        src = self._spr_walk or self._spr_attack
        if not src:
            self._spr_void = []
            return
        self._spr_void = [self._voidify(f) for f in src]
        bb = src[0].get_bounding_rect()
        self._void_head = (bb.centerx, bb.top + int(bb.height * 0.30))

    def _draw_void(self, surf, bx, by, normal_frame):
        """Dessine la FORME DU NÉANT du héros (sprite réel transformé + aura +
        yeux placés sur la VRAIE tête). u = avancée de la transformation."""
        if self._spr_void is None:
            self._build_void()
        u = max(0.0, min(1.0, self._void_u)); fr = self.frame
        vf = None; fw = PLAYER_W
        if self._spr_void:
            n = len(self._spr_void); vf = self._spr_void[(self._anim_t // 6) % n]
            fw = vf.get_width()
            hx, hy = self._void_head
            if self.facing < 0:
                vf = pygame.transform.flip(vf, True, False); hx = fw - hx
        else:
            hx, hy = fw // 2, fw // 3
        bcx, bcy = bx + fw // 2, by + fw // 2        # centre visuel (pour l'aura)
        headx, heady = bx + hx, by + hy
        # 1) AURA de néant + liseré glacial derrière.
        R = int(54 + 92 * u)
        aura = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
        for k in range(6):
            rr = int(R * (1 - k * 0.15))
            if rr > 0: pygame.draw.circle(aura, (8, 6, 20, int(40 * u)), (R + 4, R + 4), rr)
        surf.blit(aura, (bcx - R - 4, bcy - R - 4))
        rim = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(rim, (140, 200, 255, int(58 * u)), (R + 4, R + 4), R, 3)
        surf.blit(rim, (bcx - R - 4, bcy - R - 4), special_flags=pygame.BLEND_RGBA_ADD)
        # 2) SPRITE : crossfade normal → néant.
        if normal_frame is not None and u < 1.0:
            nf = normal_frame.copy()
            nf.fill((255, 255, 255, int(255 * (1 - u))), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(nf, (bx, by))
        if vf is not None:
            if u < 1.0:
                vf = vf.copy(); vf.fill((255, 255, 255, int(255 * u)), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(vf, (bx, by))
        # (Pas d'yeux ni de filaments : juste la silhouette noire au liseré bleu = le Néant.)

    def update(self, keys, platforms, particles, pull_x=None, pull_y=None, pull_force=0.0):
        self.frame += 1
        self._anim_t += 1   # compteur d'animation indépendant
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

        # ── Mise à jour de l'état d'animation walk/idle ─────────────────
        if self.hp <= 0:
            if self._anim_state != 'death':
                self._anim_state = 'death'
                self._anim_t     = 0
        elif self._anim_state not in ('attack', 'hurt', 'death'):
            moving = abs(self.vx) > 1.0
            new_state = 'walk' if moving else 'idle'
            if self._anim_state != new_state:
                self._anim_state = new_state
                self._anim_t     = 0

    def draw(self, surf, cam):
        # ── Helpers blit ─────────────────────────────────────────────────
        # Ancrage : bord gauche = rect.left, bas pied = rect.bottom
        def _blit_pos(rx, ry_bottom):
            """Retourne (blit_x, blit_y) pour blitter le frame à la bonne position."""
            return (rx      - cam[0] - SPR_BLIT_OX,
                    ry_bottom - cam[1] - SPR_BLIT_FEET_OY)


        # ── Clignotement invulnérabilité ────────────────────────────────
        if self.invuln > 0 and (self.invuln // 3) % 2 == 0:
            return

        # ── Ombre au sol ─────────────────────────────────────────────────
        # Uniquement quand on est posé sur une plateforme ET qu'on ne dash PAS.
        if self.on_ground and self.dash_timer <= 0:
            sh_cx = self.rect.centerx - cam[0]
            sh_cy = self.rect.bottom  - cam[1]          # exactement au sol
            sh_w  = int(PLAYER_W * 1.1)                 # légèrement plus large que le perso
            sh_h  = max(4, sh_w // 7)                   # très plate — juste un filet
            _sh   = pygame.Surface((sh_w, sh_h + 2), pygame.SRCALPHA)
            pygame.draw.ellipse(_sh, (0, 0, 0, 160), (0, 1, sh_w, sh_h))
            surf.blit(_sh, (sh_cx - sh_w // 2, sh_cy - sh_h // 2))

        # ── Sprite Frounette (scale ×3, ancrage pieds) ───────────────────
        frame_surf = self._get_anim_frame()
        bx, by = _blit_pos(self.rect.left, self.rect.bottom)
        if self._void_form:
            self._draw_void(surf, bx, by, frame_surf)
        elif frame_surf is not None:
            if self._anim_state == 'attack':
                # Rotation de l'animation d'attaque vers le curseur :
                #   facing=1 (droite) → rot = -aim_angle
                #   facing=-1 (gauche, frame déjà flippé) → rot = 180 - aim_angle
                aim = self._aim_angle
                if self.facing >= 0:
                    rot_deg = -math.degrees(aim)
                else:
                    rot_deg = 180.0 - math.degrees(aim)
                rotated = pygame.transform.rotate(frame_surf, rot_deg)
                # Centrer la frame pivotée sur le centre visuel du personnage
                rcx = self.rect.centerx - cam[0]
                rcy = self.rect.centery - cam[1]
                rblit = rotated.get_rect(center=(rcx, rcy))
                surf.blit(rotated, rblit)
            else:
                surf.blit(frame_surf, (bx, by))
        else:
            # Fallback procédural si assets absents
            x = self.rect.x - cam[0]
            y = self.rect.y - cam[1]
            body = pal_body(self.dimension)
            robe = pal_robe(self.dimension)
            pygame.draw.rect(surf, robe,
                             (x + 2, y + 18, self.rect.w - 4, self.rect.h - 18),
                             border_radius=6)
            pygame.draw.circle(surf, body, (x + self.rect.w // 2, y + 14), 12)
            pygame.draw.arc(surf, robe,
                            (x - 2, y - 2, self.rect.w + 4, 32),
                            math.radians(20), math.radians(160), 6)
            ex = x + self.rect.w // 2 + 3 * self.facing
            pygame.draw.circle(surf, Pal.P_EYE, (ex, y + 14), 2)

        # ── Indicateur de visée arc ─────────────────────────────────────
        # Flèche rotative depuis le centre du joueur vers le curseur.
        # Pleinement visible quand l'arc est prêt, fondu pendant le cooldown.
        aim_alpha = int(255 * max(0.0, 1.0 - self.bow_cd / BOW_COOLDOWN))
        if aim_alpha > 20 and not self._void_form:
            ang  = self._aim_angle
            # Centre de tir (légèrement devant le perso)
            hcx  = self.rect.centerx - cam[0] + int(math.cos(ang) * 6)
            hcy  = self.rect.centery - cam[1] + int(math.sin(ang) * 6)
            # Longueur du trait de visée
            L1, L2 = 10, 36          # début / fin du trait (en pixels écran)
            x1 = hcx + int(math.cos(ang) * L1)
            y1 = hcy + int(math.sin(ang) * L1)
            x2 = hcx + int(math.cos(ang) * L2)
            y2 = hcy + int(math.sin(ang) * L2)
            # Glow extérieur
            gs = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for width, ga in ((7, int(aim_alpha * 0.18)), (4, int(aim_alpha * 0.35))):
                pygame.draw.line(gs, (255, 220, 80, ga), (x1, y1), (x2, y2), width)
            # Trait principal doré
            pygame.draw.line(gs, (255, 230, 100, aim_alpha), (x1, y1), (x2, y2), 2)
            # Pointe triangulaire
            tip_a = ang
            tw = 6
            tp1 = (x2 + int(math.cos(tip_a) * tw),
                   y2 + int(math.sin(tip_a) * tw))
            tp2 = (x2 + int(math.cos(tip_a + 2.4) * tw // 2),
                   y2 + int(math.sin(tip_a + 2.4) * tw // 2))
            tp3 = (x2 + int(math.cos(tip_a - 2.4) * tw // 2),
                   y2 + int(math.sin(tip_a - 2.4) * tw // 2))
            pygame.draw.polygon(gs, (255, 255, 160, aim_alpha), [tp1, tp2, tp3])
            surf.blit(gs, (0, 0))

        # ── Aura swap de dimension ───────────────────────────────────────
        if self.swap_invuln > 0 and not self._void_form:
            t = self.swap_invuln / SWAP_INVULN_FRAMES
            r = int(28 + (1 - t) * 30)
            a = int(120 * t)
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*pal_accent(self.dimension), a),
                               (r + 2, r + 2), r, 3)
            surf.blit(s, (self.rect.centerx - cam[0] - r - 2,
                          self.rect.centery  - cam[1] - r - 2))


# ---------------------------------------------------------------------------
# Plateformes
# ---------------------------------------------------------------------------

class Platform:
    def __init__(self, x, y, w, h, dim_only=None, kind="ground"):
        self.rect = pygame.Rect(x, y, w, h)
        self.dim_only = dim_only
        self.kind = kind
        self.corrupt_t = 0        # frames de corruption restantes (0 = saine)
        self.corrupt_max = 1      # pour normaliser le rendu

    @property
    def corrupted(self):
        return self.corrupt_t > 0

    def corrupt(self, frames):
        """Aegis ronge cette plateforme : on ne peut plus s'y poser."""
        self.corrupt_t = max(self.corrupt_t, frames)
        self.corrupt_max = max(self.corrupt_max, self.corrupt_t)

    def tick(self):
        if self.corrupt_t > 0:
            self.corrupt_t -= 1

    def collides(self, dim):
        if self.corrupt_t > 0:
            return False          # plateforme corrompue : on tombe au travers
        return self.dim_only is None or self.dim_only == dim

    def draw(self, surf, cam, current_dim):
        rect = self.rect.move(-cam[0], -cam[1])
        # ── Plateforme dévorée par le Néant : éclat de vide instable ───────
        if self.corrupt_t > 0:
            # Dalle dévorée par le Néant : wireframe magenta instable, arête
            # supérieure rongée, débris qui s'élèvent → on LIT qu'elle n'est
            # plus solide (on tombe au travers).
            pulse = 0.5 + 0.5 * math.sin(self.corrupt_t * 0.28)
            fade = min(1.0, self.corrupt_t / 30.0)   # s'efface quand la corruption finit
            w, h = max(1, rect.w), max(1, rect.h)
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(s, (90, 10, 120, int(70 * fade)), (0, 0, w, h),
                             border_radius=4)
            for i in range(0, w, 15):
                hh = int(h * (0.3 + 0.7 * ((i * 7 % 11) / 11.0)))
                pygame.draw.line(s, (255, 95, 215, int((60 + 120 * pulse) * fade)),
                                 (i, 2), (i + 6, hh), 1)
            pygame.draw.rect(s, (235, 40, 165, int((120 + 100 * pulse) * fade)),
                             (0, 0, w, h), width=2, border_radius=4)
            jag = [(i, int(1 + 5 * ((i * 13 % 7) / 7.0) * pulse))
                   for i in range(0, w + 1, 8)]
            if len(jag) >= 2:
                pygame.draw.lines(s, (255, 150, 230, int(200 * fade)), False, jag, 2)
            surf.blit(s, rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)
            if (self.corrupt_t // 4) % 2 == 0:
                for k in range(3):
                    dx = (self.corrupt_t * (k + 3)) % w
                    dy = (self.corrupt_t * 2) % 16
                    pygame.draw.circle(surf, (255, 95, 215),
                                       (rect.left + dx, rect.top - dy), 2)
            return
        active = self.collides(current_dim)
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
        self.radius = 95
        self.max_hp_total = 1000   # 200 HP par phase × 5
        self.hp = self.max_hp_total
        self.phase = 1
        self.phase_count = 5
        self.display_name = "LA LUNE"
        self.state = "intro"
        self.intro_t = 0
        self.transition_t = 0
        self.next_phase = 1
        self.attack_timer = 60
        self.subattack_timer = 0
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
        self._p4_heal_spawned   = False  # orbe de soin spawné une seule fois
        self._p4_orb_wait       = 0     # frames depuis spawn de l'orbe (anti-softlock)
        self._p4_orb_collected  = False  # phase 5 locked until orb collected
        self._p5_sky_timer      = 0     # timer pluie du ciel phase 5
        self.pre_dr_active = False       # dialogue animé avant DR
        self.pre_dr_t = 0
        self.post_dr = False             # defense buff after DR (arrows deal half dmg)
        self.final_blow_active = False   # cinématique fin divine à ≤50 HP
        self.final_blow_t = 0
        self.pause_timer = 0

        # Chargement du sprite de la Lune (moon_sprite.png dans le même dossier)
        _base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        _sprite_path = os.path.join(_base_dir, "assets", "images", "moon_sprite.png")
        try:
            _raw = pygame.image.load(_sprite_path).convert_alpha()
            # Pré-scale à la taille du boss (radius*2 x radius*2)
            self._moon_sprite = pygame.transform.scale(_raw, (self.radius * 2, self.radius * 2))
        except Exception:
            self._moon_sprite = None  # fallback dessin procédural si fichier absent

        # Son de laser
        try:
            self._snd_laser = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "laser.mp3"))
            self._snd_laser.set_volume(0.15)
        except Exception:
            self._snd_laser = None

        # Son Derniers Recours
        try:
            self._snd_last_resort = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "last_resort.mp3"))
            self._snd_last_resort.set_volume(0.15)
        except Exception:
            self._snd_last_resort = None

        # Son : l'épée coupe le boss (final blow t=331)
        try:
            self._snd_sword_cut = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "sword_cut.mp3"))
            self._snd_sword_cut.set_volume(0.18)
        except Exception:
            self._snd_sword_cut = None

        # Son : explosion du boss (final blow t=331)
        try:
            self._snd_boss_explosion = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "boss_explosion.mp3"))
            self._snd_boss_explosion.set_volume(0.18)
        except Exception:
            self._snd_boss_explosion = None

        # Son : boss reçoit des dégâts
        try:
            self._snd_boss_hit = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "boss_hit.mp3"))
            self._snd_boss_hit.set_volume(0.18)
        except Exception:
            self._snd_boss_hit = None

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
        # Boss mort → plus aucune logique IA
        if self.dead:
            return
        if self.hit_flash > 0: self.hit_flash -= 1
        if self.stun_timer > 0:
            self.stun_timer -= 1
            return

        # Pause entre les animations phase 5
        if self.pause_timer > 0:
            self.pause_timer -= 1
            # Joueur invulnérable pendant les pauses (aucun dégât pendant les animations)
            if self.game.player:
                self.game.player.invuln = max(self.game.player.invuln, 10)
            if self.pause_timer == 0 and self.post_dr and not self.final_blow_active:
                self.game._play_music("boss_moon_p2.mp3")
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
                target = max(p, self.phase)
                # Phase 5 locked until heal orb from phase 4 is collected
                if target == 5 and not self._p4_orb_collected:
                    return max(4, self.phase)
                return target
        return max(1, self.phase)

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
            # Jugement Lunaire toutes les 6 attaques
            if self.attacks_since_judgment >= 6:
                self._cast_lunar_judgment(beams, telegraphs, particles, player)
                self.attacks_since_judgment = 0
                self.p1_step = 0  # repart du début après le jugement
                self.attack_timer = 170
                return
            # Séquence rotative : fan → meteor → fan → star_curtain
            P1_SEQ = ["fan", "meteor", "fan", "star_curtain"]
            choice = P1_SEQ[self.p1_step % len(P1_SEQ)]
            self.p1_step += 1
            if choice == "fan":
                self._tg_crescent_fan(player, projectiles, telegraphs, dim=DIM_REAL, hits_any_dim=True)
                self.attack_timer = 120  # 2 sec
            elif choice == "meteor":
                self._tg_meteor_targets(player, projectiles, telegraphs, particles, hits_any_dim=True)
                self.attack_timer = 120  # 2 sec
            else:  # star_curtain
                self._tg_star_curtain(player, projectiles, telegraphs, hits_any_dim=True)
                self.attack_timer = 120  # 2 sec

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
        cascade_delay = 50
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
                    if self._snd_laser: self._snd_laser.play()
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
            self.dim_timer = 170
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
                self.attack_timer = 58
            elif choice == "homing":
                # Réduit à 2 orbes (une par dimension)
                self._fire_homing_orb(player, projectiles, DIM_REAL)
                self._fire_homing_orb(player, projectiles, DIM_DREAM)
                self._fire_homing_orb(player, projectiles, self.dim)
                self.attack_timer = 42
            else:  # fan_dim
                self._tg_crescent_fan(player, projectiles, telegraphs, dim=self.dim, count=10)
                self.attack_timer = 44

    # ---- PHASE 3 : L'ÉCLIPSE ----
    def _update_p3(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "tense"
        self._drift_to(self.cx, self.target_y - 30, 1.7)
        self.attack_timer -= 1
        if self.attack_timer <= 0:
            px, py = player.rect.centerx, player.rect.centery
            step = self.p3_step % 7
            self.p3_step += 1
            if step == 0:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=48, width=85, dmg=3, hits_any_dim=True)
                tx2 = max(self.ax_left + 100, min(self.ax_right - 100, px + 250))
                self._tg_beam_vertical(tx2, beams, telegraphs, dim=DIM_REAL, duration=48, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 50
            elif step == 1:
                ty = max(120, min(580, py))
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=48, height=70, dmg=3, hits_any_dim=True)
                ty2 = max(120, min(580, py + 130))
                self._tg_beam_horizontal(ty2, beams, telegraphs, dim=DIM_REAL, duration=48, height=70, dmg=3, hits_any_dim=True)
                self.attack_timer = 50
            elif step == 2:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + 220))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=44, width=85, dmg=3, hits_any_dim=True)
                tx2 = max(self.ax_left + 100, min(self.ax_right - 100, px + 400))
                self._tg_beam_vertical(tx2, beams, telegraphs, dim=DIM_REAL, duration=44, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 46
            elif step == 3:
                ty = max(120, min(580, py - 110))
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=44, height=70, dmg=3, hits_any_dim=True)
                ty2 = max(120, min(580, py + 130))
                self._tg_beam_horizontal(ty2, beams, telegraphs, dim=DIM_REAL, duration=44, height=70, dmg=3, hits_any_dim=True)
                self.attack_timer = 46
            elif step == 4:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px - 220))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=44, width=85, dmg=3, hits_any_dim=True)
                tx2 = max(self.ax_left + 100, min(self.ax_right - 100, px - 400))
                self._tg_beam_vertical(tx2, beams, telegraphs, dim=DIM_REAL, duration=44, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 46
            elif step == 5:
                # Croix finale — 2 verticaux + 2 horizontaux couvrent les deux dimensions
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-50, 50)))
                tx2 = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-50, 50) + 200))
                ty = max(120, min(580, py + random.randint(-30, 30)))
                ty2 = max(120, min(580, py + random.randint(-30, 30) + 130))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=44, width=75, dmg=3, hits_any_dim=True)
                self._tg_beam_vertical(tx2, beams, telegraphs, dim=DIM_REAL, duration=44, width=75, dmg=3, hits_any_dim=True)
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=44, height=65, dmg=3, hits_any_dim=True)
                self._tg_beam_horizontal(ty2, beams, telegraphs, dim=DIM_REAL, duration=44, height=65, dmg=3, hits_any_dim=True)
                self.attack_timer = 60
            else:  # step 6 — TRIPLE CROIX
                for dx in (-280, 0, 280):
                    tx3 = max(self.ax_left + 100, min(self.ax_right - 100, px + dx))
                    self._tg_beam_vertical(tx3, beams, telegraphs, dim=DIM_REAL, duration=44, width=80, dmg=3, hits_any_dim=True)
                for dy2 in (-120, 120):
                    ty3 = max(120, min(580, py + dy2))
                    self._tg_beam_horizontal(ty3, beams, telegraphs, dim=DIM_REAL, duration=44, height=65, dmg=3, hits_any_dim=True)
                self.attack_timer = 50

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
            # Spawn orbe de soin une seule fois quand tous les fragments meurent
            if not self._p4_heal_spawned:
                self._p4_heal_spawned = True
                self.game.heal_orbs.append(HealOrb(self.cx, self.cy - 60, amount=5))
            # Anti-softlock : si le joueur n'a pas ramassé l'orbe après 600 frames,
            # on déverrouille la phase 5 automatiquement
            if not self._p4_orb_collected:
                self._p4_orb_wait += 1
                if self._p4_orb_wait >= 600:
                    self._p4_orb_collected = True
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
            self.attack_timer = max(25, 55 - 10 * (4 - len(alive)))

    # ---- PHASE 5 : LE CROISSANT INVERSÉ — CHORÉGRAPHIE EN 6 ÉTAPES ----
    def _update_p5(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "rage"

        # ── FINAL BLOW : déclenché au 2ème DR (post_dr=True, hp≤50) ─────────
        if (self.post_dr and self.hp <= 50 and
                not self.final_blow_active and not self.pre_dr_active):
            self.pause_timer = 0
            self.final_blow_active = True
            self.final_blow_t = 0
            self._lr_ox = self.x
            self._lr_oy = self.y
            self.game.add_shake(30, 60)
            try:
                pygame.mixer.music.fadeout(2000)
            except Exception:
                pass
            return

        if self.final_blow_active:
            self._update_final_blow(beams, particles, player)
            return

        # ── PRÉ-DR : dialogue animé avant Derniers Recours ───────────────────
        if (self.hp < 100 and not self.last_resort_done and
                not self.pre_dr_active and not self.final_blow_active):
            self.pre_dr_active = True
            self.pre_dr_t = 0
            self._lr_ox = self.x
            self._lr_oy = self.y
            self.game.add_shake(18, 30)
            return

        if self.pre_dr_active:
            self._update_pre_dr(player)
            return

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
            self.dim_timer = 55 if self.final_form else 80

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
                # Étape 0 — DOUBLE CROIX : 2 verticaux + 2 horizontaux simultanés
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-70, 70)))
                tx2 = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-70, 70) + 200))
                ty = max(130, min(570, py + random.randint(-35, 35)))
                ty2 = max(130, min(570, py + random.randint(-35, 35) - 100))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=65, width=82, dmg=3, hits_any_dim=True, red=True)
                self._tg_beam_vertical(tx2, beams, telegraphs, dim=DIM_REAL, duration=65, width=82, dmg=3, hits_any_dim=True, red=True)
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=65, height=68, dmg=3, hits_any_dim=True, red=True)
                self._tg_beam_horizontal(ty2, beams, telegraphs, dim=DIM_REAL, duration=65, height=68, dmg=3, hits_any_dim=True, red=True)
                self.attack_timer = int(58 * spd)

            elif step == 1:
                # Étape 1 — GRAND ÉVENTAIL
                count = 13 if self.final_form else 10
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=self.dim, count=count, spread_deg=140)
                self.attack_timer = int(46 * spd)

            elif step == 2:
                # Étape 2 — ORBES GUIDÉES
                self._fire_homing_orb(player, projectiles, DIM_REAL)
                self._fire_homing_orb(player, projectiles, DIM_DREAM)
                self._fire_homing_orb(player, projectiles, self.dim)
                if self.final_form:
                    self._fire_homing_orb(player, projectiles, self.dim)
                self.attack_timer = int(44 * spd)

            elif step == 3:
                # Étape 3 — GASTERS CARDINAUX
                n = 7 if self.final_form else 5
                self._cast_gaster_blasters(player, beams, telegraphs, particles, n=n)
                self.attack_timer = int(52 * spd)

            elif step == 4:
                # Étape 4 — DOUBLE RIDEAU D'ÉTOILES
                self._tg_star_curtain(player, projectiles, telegraphs, hits_any_dim=True)
                self._tg_star_curtain(player, projectiles, telegraphs, hits_any_dim=True)
                self.attack_timer = int(58 * spd)

            else:
                # Étape 5 — DOUBLE ÉVENTAIL (real + dream simultanés) → fin de cycle
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=DIM_REAL, count=8, spread_deg=120)
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=DIM_DREAM, count=8, spread_deg=120)
                self.attack_timer = int(44 * spd)


        # ── ORBE PARRY : cadence fixe, toujours viseuse → apprenable ──
        self.subattack_timer -= 1
        if self.subattack_timer <= 0:
            self._fire_parry_orb(player, projectiles)
            self.subattack_timer = int(28 * (0.55 if self.final_form else 0.85))

        # ── PLUIE DU CIEL (final form uniquement) ──
        if self.final_form:
            self._p5_sky_timer -= 1
            if self._p5_sky_timer <= 0:
                self._cast_sky_gaster_rain(player, beams, telegraphs, particles)
                self._p5_sky_timer = 65

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
                                      color=(255, 130, 200), red=True))
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
                                      color=(255, 180, 220), red=True))
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
                                    hits_any_dim=hits_any_dim,
                                    x=ox, y=oy,
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
                                        hits_any_dim=hits_any_dim, x=tx, y=ty, r=40))

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
            if self._snd_laser: self._snd_laser.play()
        telegraphs.append(Telegraph("beam_h", 50, dim, on_fire=fire,
                                    y=y, left=left, right=right,
                                    final_height=60))

    def _tg_beam_vertical(self, x, beams, telegraphs, dim=DIM_REAL, duration=70, width=70, dmg=3, hits_any_dim=False, red=False):
        def fire():
            rect = pygame.Rect(int(x - width / 2), self.ay_top,
                               int(width), self.ay_bottom - self.ay_top + 400)
            beams.append(Beam(rect, dim, life=22, dmg=dmg, hits_any_dim=hits_any_dim, red=red))
            if self._snd_laser: self._snd_laser.play()
        telegraphs.append(Telegraph("beam_v", duration, dim, on_fire=fire,
                                    x=x, top=self.ay_top, bottom=self.ay_bottom + 400,
                                    final_width=width, hits_any_dim=hits_any_dim))

    def _tg_beam_horizontal(self, y, beams, telegraphs, dim=DIM_REAL, duration=70, height=60, dmg=3, hits_any_dim=False, red=False):
        def fire():
            rect = pygame.Rect(self.ax_left, int(y - height / 2),
                               self.ax_right - self.ax_left, int(height))
            beams.append(Beam(rect, dim, life=22, dmg=dmg, hits_any_dim=hits_any_dim, red=red))
            if self._snd_laser: self._snd_laser.play()
        telegraphs.append(Telegraph("beam_h", duration, dim, on_fire=fire,
                                    y=y, left=self.ax_left, right=self.ax_right,
                                    final_height=height, hits_any_dim=hits_any_dim))

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

    def _update_final_blow(self, beams, particles, player):
        """Cinématique fin — épée divine fend le boss en deux : 590 frames (~10 sec).

        Timeline :
          A   1- 60  : boss tremble, feu intense
          B  61-110  : silence, le monde se fige
          C 111-165  : épée matérialise depuis le ciel
          D 166-200  : épée accélère
         D2 201-210  : fissure, épée touche
        WAT 211-330  : épée figée dans le boss, "?" sur l'expression (2 sec)
          E 331-350  : IMPACT — boss se brise
          F 351-590  : moitiés tombent, débris (4 sec)
        FIN  >590   : fin
        """
        self.final_blow_t += 1
        t = self.final_blow_t

        # Joueur invulnérable pendant toute la cinématique
        player.invuln = max(player.invuln, 10)
        self.face_state = "open"

        # Vider les projectiles actifs dès le début
        if t == 1:
            self.game.projectiles_boss.clear()
            self.game.beams.clear()
            self.game.rings.clear()
            self.game.telegraphs.clear()
            self.game.add_shake(18, 50)
            self.game.announce_phase("DERNIERS RECOURS…")

        # ── Phase A (1-60) : boss tremble, feu de plus en plus intense ────────
        if t <= 60:
            shake_amp = min(16.0, t * 0.32)
            self.x = self._lr_ox + random.uniform(-shake_amp, shake_amp)
            self.y = self._lr_oy + random.uniform(-shake_amp, shake_amp)
            if t % 4 == 0:
                burst(particles, self.x, self.y, 22, (255, 40, 10), 10.0, 32, 0.0, 5)
            if t % 8 == 0:
                burst(particles, self.x, self.y, 12, (255, 180, 40), 7.0, 26, 0.0, 4)
            if t % 12 == 0:
                burst(particles, self.x, self.y, 8, (255, 240, 120), 5.0, 22, 0.0, 3)
                self.game.add_shake(min(20, t // 3), 8)

        # ── Phase B (61-110) : silence — le monde se fige ────────────────────
        elif t <= 110:
            self.x = self._lr_ox + random.uniform(-1.5, 1.5)
            self.y = self._lr_oy + random.uniform(-1.5, 1.5)
            if t == 61:
                self.game.add_shake(8, 16)
            if t % 15 == 0:
                for _ in range(4):
                    burst(particles,
                          self._lr_ox + random.uniform(-60, 60),
                          self._lr_oy - 80,
                          2, (255, 240, 180), 1.2, 55, 0.12, 2)

        # ── Phase C (111-165) : l'épée matérialise depuis le ciel ────────────
        elif t <= 165:
            self.x = self._lr_ox
            self.y = self._lr_oy
            if t == 111:
                self.game.add_shake(12, 22)
                self.game.start_slowmo(30)
                self.game._play_music("final_cinematic.mp3", fadein_ms=1500)
            prog_c = (t - 111) / 54.0
            self.game.sword_visible = True
            boss_sy = int(self._lr_oy - self.game.cam[1])
            self.game.sword_x = int(self._lr_ox - self.game.cam[0])
            self.game.sword_y = int(-180 + prog_c * (boss_sy - 120 + 180))
            if t % 7 == 0:
                for _ in range(5):
                    ox = random.uniform(-28, 28)
                    burst(particles,
                          self._lr_ox + ox, self._lr_oy - 120,
                          3, (255, 245, 160), 2.5, 85, 0.1, 2)

        # ── Phase D (166-200) : l'épée accélère vers le boss ─────────────────
        elif t <= 200:
            self.x = self._lr_ox
            self.y = self._lr_oy
            prog_d = ((t - 166) / 34.0) ** 2.0
            boss_sy = int(self._lr_oy - self.game.cam[1])
            self.game.sword_x = int(self._lr_ox - self.game.cam[0])
            start_y = boss_sy - 120
            self.game.sword_y = int(start_y + prog_d * (boss_sy - start_y - 8))
            if t % 5 == 0:
                burst(particles, self._lr_ox, self._lr_oy - 30,
                      10, (200, 230, 255), 5.5, 18, 0.0, 3)

        # ── Phase D2 (201-210) : fissure sur le boss, épée touche ────────────
        elif t <= 210:
            self.x = self._lr_ox
            self.y = self._lr_oy
            self.game.boss_crack_active = True
            prog_d2 = (t - 201) / 9.0
            boss_sy = int(self._lr_oy - self.game.cam[1])
            self.game.sword_x = int(self._lr_ox - self.game.cam[0])
            self.game.sword_y = int(boss_sy - 8 + prog_d2 * 16)
            if t % 3 == 0:
                self.game.add_shake(4, 4)
                burst(particles, self._lr_ox, self._lr_oy,
                      6, (255, 255, 200), 3.0, 12, 0.0, 3)

        # ── Phase WAIT (211-330) : épée figée, boss confus — "?" apparaît ────
        elif t <= 330:
            self.x = self._lr_ox
            self.y = self._lr_oy
            if t == 211:
                self.game.boss_crack_active = False
                self.game.boss_qmark_t = 1
            # Épée légèrement vibrante, plantée dans le boss
            boss_sy = int(self._lr_oy - self.game.cam[1])
            self.game.sword_visible = True
            jitter = math.sin(t * 0.55) * 1.8
            self.game.sword_x = int(self._lr_ox - self.game.cam[0] + jitter)
            self.game.sword_y = int(boss_sy + 8)
            # Timer pour le point d'interrogation
            self.game.boss_qmark_t += 1
            # Quelques étincelles dorées qui tombent de la garde
            if t % 14 == 0:
                burst(particles, self._lr_ox, self._lr_oy - 50,
                      4, (255, 230, 80), 2.0, 55, 0.12, 2)

        # ── Phase E (331-350) : IMPACT — le boss se brise ────────────────────
        elif t <= 350:
            self.x = self._lr_ox
            self.y = self._lr_oy
            if t == 331:
                self.game.sword_visible = False
                self.game.boss_crack_active = False
                self.game.boss_qmark_t = 0
                self.game.boss_split_t = 1
                self.game.boss_split_cx = self._lr_ox
                self.game.boss_split_cy = self._lr_oy
                self.game.add_shake(90, 110)
                self.game.start_slowmo(65)
                self.game.announce_phase("CE N'EST PAS LE MOMENT")
                if self._snd_sword_cut: self._snd_sword_cut.play()
                if self._snd_boss_explosion: self._snd_boss_explosion.play()
                for _ in range(220):
                    angle = random.uniform(math.pi * 0.55, math.pi * 0.95)
                    spd   = random.uniform(8.0, 30.0)
                    col   = random.choice([(255, 255, 220), (255, 220, 80), (255, 190, 50)])
                    vx = math.cos(angle) * spd
                    vy = -abs(math.sin(angle) * spd * 0.8)
                    particles.append(Particle(self.x, self.y, vx, vy,
                                              random.randint(55, 130), col,
                                              random.randint(4, 9), 0.06))
                for _ in range(220):
                    angle = random.uniform(math.pi * 0.05, math.pi * 0.45)
                    spd   = random.uniform(8.0, 30.0)
                    col   = random.choice([(255, 255, 220), (255, 220, 80), (255, 190, 50)])
                    vx = math.cos(angle) * spd
                    vy = -abs(math.sin(angle) * spd * 0.8)
                    particles.append(Particle(self.x, self.y, vx, vy,
                                              random.randint(55, 130), col,
                                              random.randint(4, 9), 0.06))
                burst(particles, self.x, self.y, 160, (255, 255, 255), 34.0, 55, 0.0, 9)
                burst(particles, self.x, self.y, 90, (200, 230, 255), 24.0, 42, 0.0, 7)
            if self.game.boss_split_t > 0:
                self.game.boss_split_t += 1

        # ── Phase F (351-590) : moitiés tombent, débris dorés (4 sec) ────────
        elif t <= 590:
            self.x = self._lr_ox
            self.y = self._lr_oy
            if self.game.boss_split_t > 0:
                self.game.boss_split_t += 1
            if t < 540 and t % 9 == 0:
                burst(particles,
                      self.x + random.uniform(-75, 75),
                      self.y + random.uniform(-55, 55),
                      22, (255, 215, 80), 7.5, 52, 0.08, 4)
                self.game.add_shake(max(3, 15 - (t - 351) // 6), 5)

        # ── FIN (>590) ────────────────────────────────────────────────────────
        else:
            self.game.sword_visible = False
            self.game.boss_crack_active = False
            self.game.boss_qmark_t = 0
            self.game.boss_split_t = 0
            self.final_blow_active = False
            self.dead = True
            self.game.final_blow_hub_t = 1

    def _update_pre_dr(self, player):
        """Dialogue animé du boss avant Derniers Recours (~120 frames)."""
        self.pre_dr_t += 1
        t = self.pre_dr_t

        # Le joueur est invulnérable pendant toute l'animation
        player.invuln = max(player.invuln, 10)

        # Boss tremble
        shake_amp = min(10.0, t * 0.15)
        self.x = self._lr_ox + random.uniform(-shake_amp, shake_amp)
        self.y = self._lr_oy + random.uniform(-shake_amp, shake_amp)
        self.face_state = "rage"

        if t % 8 == 0:
            burst(self.game.particles, self._lr_ox, self._lr_oy, 12,
                  (220, 40, 20), 7.0, 22, 0.0, 4)

        # Signal au jeu pour le zoom/dialogue
        self.game.pre_dr_zoom_t = t

        # Fin → lancer DR
        if t >= 120:
            self.pre_dr_active = False
            self.last_resort_done = True
            self.last_resort_active = True
            self.last_resort_t = 0
            self.game.pre_dr_zoom_t = 0
            self.game.add_shake(24, 60)
            self.game.start_slowmo(35)
            if self._snd_last_resort: self._snd_last_resort.play()

    def _update_last_resort(self, beams, telegraphs, particles):
        self.last_resort_t += 1
        t = self.last_resort_t

        # ── PHASE A : CRISE (t 0-50) — boss crie, tremble intensément ──
        if t == 1:
            # Mémorise position d'origine
            self._lr_ox = self.x
            self._lr_oy = self.y
            self.game.announce_phase("DERNIERS RECOURS")

        if t < 50:
            self.face_state = "open"
            # Tremblement du boss : oscille autour de sa position
            shake_amp = min(12.0, t * 0.3)
            self.x = self._lr_ox + random.uniform(-shake_amp, shake_amp)
            self.y = self._lr_oy + random.uniform(-shake_amp, shake_amp)
            if t % 5 == 0:
                burst(particles, self._lr_ox, self._lr_oy, 28, (255, 60, 20), 10.0, 32, 0.0, 5)
                self.game.add_shake(min(20, int(t * 0.5)), 8)
            if t % 12 == 0:
                burst(particles, self._lr_ox, self._lr_oy, 18, (255, 200, 50), 8.0, 24, 0.0, 4)

        # ── PHASE B : SORTIE (t 50-110) — boss fonce vers le haut hors-écran ──
        elif t < 110:
            self.face_state = "rage"
            progress = (t - 50) / 60.0
            # Accélération exponentielle vers le haut
            self.y = self._lr_oy - (progress ** 2) * 900
            self.x = self._lr_ox + math.sin(t * 0.4) * 20
            if t % 4 == 0:
                burst(particles, self.x, self.y, 12, (255, 80, 30), 7.0, 18, 0.05, 3)
            if t == 50:
                self.game.add_shake(25, 20)

        # ── PHASE C : VIDE (t 110-155) — boss hors-écran, silence avant la tempête ──
        elif t < 155:
            self.x = self._lr_ox
            self.y = -300  # bien caché hors-écran
            if t % 18 == 0:
                self.game.add_shake(8, 6)

        # ── PHASE D : RETOUR (t 155-185) — boss plonge depuis le ciel ──
        elif t < 185:
            progress = (t - 155) / 30.0
            # Décélération : arrive vite puis freine
            ease = 1.0 - (1.0 - progress) ** 3
            self.x = self._lr_ox
            self.y = -300 + ease * (self._lr_oy + 300)
            if t % 3 == 0:
                burst(particles, self.x, self.y + 40, 18, (255, 40, 10), 9.0, 22, 0.05, 4)

        # ── PHASE E : IMPACT + RAYON (t=185) ──
        elif t == 185:
            self.x = self._lr_ox
            self.y = self._lr_oy
            # Explosion d'impact
            burst(particles, self.x, self.y, 120, (255, 80, 20), 16.0, 70, 0.0, 6)
            burst(particles, self.x, self.y, 80, (255, 220, 60), 12.0, 55, 0.0, 5)
            self.game.add_shake(45, 70)
            self.game.start_slowmo(40)
            if self._snd_laser: self._snd_laser.play()
            # Rayon colossal toute l'arène
            rect = pygame.Rect(int(self.ax_left),
                               int(self.ay_top),
                               int(self.ax_right - self.ax_left),
                               int(self.ay_bottom - self.ay_top + 600))
            beams.append(Beam(rect, DIM_REAL, life=70, dmg=10,
                              hits_any_dim=True, color=(255, 50, 20), red=True, once=True))
            # Faisceaux secondaires décoratifs
            for _off in (-50, 50):
                r2 = pygame.Rect(
                    int(self.ax_left + abs(_off)),
                    int(self.ay_top),
                    int(self.ax_right - self.ax_left - abs(_off) * 2),
                    int(self.ay_bottom - self.ay_top + 600)
                )
                beams.append(Beam(r2, DIM_REAL, life=60, dmg=0,
                                  hits_any_dim=False, red=True))
            # Faisceau horizontal en croix
            rect_h = pygame.Rect(
                int(self.ax_left),
                int(self._lr_oy) - 40,
                int(self.ax_right - self.ax_left),
                80
            )
            beams.append(Beam(rect_h, DIM_REAL, life=60, dmg=0,
                               hits_any_dim=True, red=True, once=False))

        # ── PHASE F : AFTERMATH court (t 186-260) ──
        elif t < 260:
            self.x = self._lr_ox
            self.y = self._lr_oy
            if t < 220 and t % 8 == 0:
                burst(particles, self.x, self.y, 20, (255, 60, 20), 8.0, 28, 0.05, 4)
                self.game.add_shake(8, 8)

        # ── FIN : full heal, renaissance maudite ──
        if t >= 260:
            self.pause_timer = 120
            try:
                pygame.mixer.music.fadeout(2500)
            except Exception:
                pass
            self.last_resort_active = False
            self.post_dr = True
            # Full heal dans la plage phase 5 (sans bonus HP)
            self.hp = int(self.max_hp_total * PHASE_THRESHOLDS[5])  # 200 HP
            # Le joueur récupère aussi tous ses PV
            if self.game.player:
                self.game.player.hp = self.game.player.max_hp
                self.game.player.shield = 0
            self.game.announce_phase("RENAISSANCE MAUDITE")
            self.game.add_shake(30, 40)
            burst(particles, self.x, self.y, 80, (255, 30, 60), 12.0, 60, 0.0, 6)
            burst(particles, self.x, self.y, 40, (255, 255, 200), 10.0, 50, 0.0, 5)
            self.game.post_dr_dialog_t = 1

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
            self.pause_timer = 120 if self.phase == 5 else 0
            self.attack_timer = 60
            self.subattack_timer = 40
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
                self.game.p5_cinematic_t = 180

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
        if self.final_blow_active: return 0   # invincible pendant l'animation finale
        actual = dmg
        if self.phase == 5:
            actual = int(dmg * 1.6) + 1
        self.hp -= actual
        if self.post_dr:
            # Phase post-renaissance : le boss ne meurt pas par les dégâts,
            # seulement via le final blow quand hp≤50
            if self.hp < 1: self.hp = 1
        else:
            if self.hp < 0: self.hp = 0
            if self.hp == 0 and self.phase == 5:
                self.dead = True
        self.hit_flash = 8
        if self._snd_boss_hit: self._snd_boss_hit.play()
        return actual

    def draw(self, surf, cam, current_dim):
        # Invisible dès l'explosion de la cinématique finale (phase E, t=331)
        if self.final_blow_active and self.final_blow_t >= 331:
            return
        if self.dead:
            return

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
            glow_col = (220, 30, 60) if not self.final_form else (255, 10, 20)
        s = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*glow_col, 50), (self.radius * 2, self.radius * 2), self.radius * 2)
        pygame.draw.circle(s, (*glow_col, 80), (self.radius * 2, self.radius * 2), int(self.radius * 1.4))
        surf.blit(s, (cx - self.radius * 2, cy - self.radius * 2))

        if self.phase == 5:
            pulse_a = int(30 + 25 * math.sin(self.bob_t * 0.18))
            aura_r = self.radius * 3
            aura_s = pygame.Surface((aura_r * 2, aura_r * 2), pygame.SRCALPHA)
            aura_col = (255, 20, 40) if self.final_form else (200, 30, 80)
            pygame.draw.circle(aura_s, (*aura_col, pulse_a), (aura_r, aura_r), aura_r)
            surf.blit(aura_s, (cx - aura_r, cy - aura_r))
            # Anneaux de corruption rayonnants
            ring_prog = (self.bob_t * 0.12) % 1.0
            for ri in range(3):
                rp = (ring_prog + ri / 3) % 1.0
                rr = int(self.radius * (1.2 + rp * 2.2))
                ra = int(60 * (1.0 - rp))
                if ra > 4:
                    rs = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(rs, (*aura_col, ra), (rr + 2, rr + 2), rr, 2)
                    surf.blit(rs, (cx - rr - 2, cy - rr - 2))

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
                    tint.fill((140, 0, 8))     # Final form : rouge sang intense
                else:
                    tint.fill((80, 0, 10))     # Phase 5 : rouge sombre
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
                col_main = (220, 30, 60) if not self.final_form else (255, 10, 30)
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


# ===========================================================================
# AEGIS — Boss final, 7 phases
# ===========================================================================
AEGIS_PHASE_THRESHOLDS = {1: 1.00, 2: 6/7, 3: 5/7, 4: 4/7, 5: 3/7, 6: 2/7, 7: 1/7}
AEGIS_PHASE_HP_RANGES  = {
    1: (1200, 1400), 2: (1000, 1200), 3: (800, 1000), 4: (600, 800),
    5: (400, 600),   6: (200, 400),   7: (0, 200),
}
AEGIS_PHASE_NAMES = {
    1: "L'ANGE GARDIEN",
    2: "LA FISSURE",
    3: "LE MENSONGE EXPOSÉ",
    4: "LE VIDE RÉVÉLÉ",
    5: "L'HÉRITAGE VOLÉ",
    6: "DERNIER RECOURS",
    7: "LE NÉANT ABSOLU",
}
# Couleurs par forme
_AEGIS_COL_LIGHT = (255, 220, 130)   # angélique (or)
_AEGIS_COL_MIXED = (225, 110, 210)   # transition (le masque se fissure)
_AEGIS_COL_DARK  = (235, 40, 165)    # vrai visage : magenta « splat art »
_AEGIS_COL_DARK2 = (255, 95, 215)    # rose vif — éclats / cœur
_AEGIS_COL_VOID  = (120, 12, 150)    # violet profond — ombres du vide


class AegisBoss:
    """Boss final. Réutilise les primitives globales (Beam/BossProjectile/Ring/
    Telegraph) et l'infra de combat de STATE_MOON. 7 phases."""

    def __init__(self, center_x, center_y, game):
        self.game = game
        self.cx = center_x; self.cy = center_y
        self.x = center_x; self.y = -160
        self.target_x = center_x; self.target_y = center_y - 150
        self.radius = 100          # hitbox (agrandi avec le sprite)
        self.vis = 215             # rayon visuel du sprite (DIEU colossal)
        self.max_hp_total = 1400   # 200 HP × 7 phases
        self.hp = self.max_hp_total
        self.phase = 1
        self.phase_count = 2   # 2 phases VISIBLES (I avant COURROUX, II après)
        self.display_name = "AEGIS"
        self.state = "intro"
        self.intro_t = 0
        self.transition_t = 0
        self.next_phase = 1
        self.attack_timer = 60
        self.step = 0
        # ── Dynamisme « façon Sans » : aucun ordre d'attaque mémorisable ────
        self._last_pick = None      # dernier token joué (anti-répétition)
        self._recent = []           # 3 derniers tokens (anti-routine)
        self._tempo_chain = 0       # rafales d'attaques quasi instantanées restantes
        self._dodge_streak = 0      # attaques esquivées d'affilée → agressivité montante
        self._last_player_hp = None
        self._blink_cd = 0          # cooldown du Trait du Néant (blink-beam)
        self._taunts = [
            "Tu danses bien… continue.", "Trop lent.",
            "Je vois chacun de tes pas.", "Encore debout ?",
            "Tu n'esquiveras pas le Néant.",
        ]
        self.emitter = None        # attaque canalisée en cours (dict) ou None
        self.spin = 0.0            # angle accumulé pour les spirales
        self.spin2 = 0.0           # second angle (contre-rotation)
        self.lasers = []           # RotLaser actifs (Lasers Horloge)
        self.minions = []          # VoidSpawn actifs (Invocations du Vide)
        self.pools = []            # CorrosionPool actives (La Corrosion du Vide)
        self._cast_anim = 0        # flourish de canalisation (animation d'attaque)
        self._cast_col = _AEGIS_COL_DARK2
        self._combo_cd = 0         # anti-spam de l'Enchaînement Divin
        # ── Cinématique de l'Enchaînement Divin (cadrage façon Sans) ─────────
        self._cine_active = False  # True pendant toute la cinématique de combo
        self._cine_t = 0           # frame courante de la cinématique
        self._cine_dur = 1         # durée totale (barrage + entrée/sortie bandes)
        self._cine_name = ""       # titre claqué dans le letterbox
        self._cine_wave = 0        # vague en cours (compteur dramatique)
        self._cine_waves = 1       # nb total de vagues du barrage
        # ── NÉMÉSIS : cinématique d'OUVERTURE de la PHASE 7 (35 s, scriptée) ──
        # Entièrement non-interactive : le héros est gelé puis soulevé par Aegis,
        # broyé entre un trou noir et un trou blanc, et ressort à 1 PV.
        self.nemesis_active = False
        self.nemesis_t = 0
        self.nemesis_dur = 3000    # 50 s @ 60 fps (AUCUN slow-mo : tient pile 50 s)
        self.nemesis_fired = False # ne se déclenche qu'une seule fois
        self._nem_px = 0.0         # position monde interpolée du héros soulevé
        self._nem_py = 0.0
        self._nem_gx = 0.0         # ancrage sol du héros (avant la lévitation)
        self._nem_gy = 0.0
        self._nem_hp_set = False   # héros réduit à 1 PV à la détonation
        self._nem_spikes = []      # pics du SOL (base_x, base_y, ang, len, birth)
        self._nem_slabs = []       # plateformes conjurées (cx, cy, w, h, birth, hit_t)
        self._nem_slam_pts = []    # trajectoire de projection (t_abs, x, y, kind)
        self._nem_impact_t = -999  # frame du dernier impact (pour la secousse)
        self._nem_impact_xy = (0.0, 0.0)  # lieu du dernier impact (éclat radial)
        self._nem_recoil = (0.0, 0.0)     # direction de rebond après impact
        # ── COURROUX : cinématique d'attaque de la PHASE 4 (50 s, scriptée) ──
        # Le masque angélique se brise ; Aegis déchaîne sa rage, sa brutalité et
        # sa puissance (pression, déluge de météores, écrasement colossal).
        self.courroux_active = False
        self.courroux_t = 0
        self.courroux_dur = 3000   # 50 s @ 60 fps (aucun slow-mo : tient pile 50 s)
        self.courroux_fired = False
        self._cx_gx = 0.0          # ancrage du héros (cloué au sol)
        self._cx_gy = 0.0
        self._cx_hp_set = False
        self._cx_impact_t = -999   # dernier impact (secousse)
        self._cx_impact_amp = 0.0
        self._cx_meteors = []      # météores : [x, y, vx, vy, life]
        # ── FINALE : LA VRAIE FIN DU JEU (après la mort en phase 7) ──────────
        # Aegis refuse de finir : il ressurgit dans le Néant. Le héros n'a plus
        # de pouvoir (esquive seule) + UNE compétence « ?! ». Quand il l'utilise,
        # le temps s'arrête, le dieu épuisé est coupé en deux → texte final.
        self.finale_active = False
        self.finale_fired = False
        self.finale_act = "prelude"   # prelude / dialogue / survival / timestop / ending
        self.finale_t = 0             # frame dans l'acte courant
        self.finale_fire_t = 0        # horloge de tir pendant la survie
        self._fin_cut = False         # le coup fatal a été porté
        self.invuln_t = 0
        self.dim = DIM_REAL
        self.dead = False
        self.death_t = 0
        self.float_offset = 0.0
        self.bob_t = 0.0
        self.hit_flash = 0
        self.stun_timer = 0
        self._anim_t = 0
        # Attributs requis par l'infra partagée (update_moon / draw_boss_ui)
        self.last_resort_active = False
        self.last_resort_t = 0
        self.post_dr = False
        self.pre_dr_active = False
        self.final_blow_active = False
        self.final_form = False
        self._p4_orb_collected = True   # pas d'orbe de soin chez Aegis
        # Bornes d'arène (identiques à la Lune)
        self.ax_left = -180; self.ax_right = 1480
        self.ay_top = -200;  self.ay_bottom = 720
        # Son hit (réutilise celui de la Lune si dispo)
        _base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        try:
            self._snd_hit = pygame.mixer.Sound(
                _asset_path("assets", "sounds", "boss_hit.mp3"))
            self._snd_hit.set_volume(0.18)
        except Exception:
            self._snd_hit = None

    # ── Propriétés / helpers ───────────────────────────────────────────────
    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius,
                           self.radius * 2, self.radius * 2)

    def center(self):
        return (int(self.x), int(self.y))

    def _form(self):
        """Forme visuelle selon la phase."""
        if self.phase <= 2: return 'light'
        if self.phase == 3: return 'mixed'
        return 'dark'

    def _form_color(self):
        return {'light': _AEGIS_COL_LIGHT, 'mixed': _AEGIS_COL_MIXED,
                'dark': _AEGIS_COL_DARK}[self._form()]

    def _drift_to(self, tx, ty, speed=2.0):
        dx = tx - self.x; dy = ty - self.y
        d = math.hypot(dx, dy)
        if d > speed:
            self.x += dx / d * speed
            self.y += dy / d * speed
        else:
            self.x, self.y = tx, ty

    # ── Update principal ───────────────────────────────────────────────────
    def update(self, player, beams, projectiles, rings, telegraphs, particles):
        self.bob_t += 0.04
        self._anim_t += 1
        if self._cast_anim > 0: self._cast_anim -= 1
        if self._combo_cd > 0: self._combo_cd -= 1
        # Avance la cinématique de l'Enchaînement Divin ; se clôt seule à la fin.
        if self._cine_active:
            self._cine_t += 1
            if self._cine_t >= self._cine_dur:
                self._cine_active = False
                self._cine_t = 0
        # NÉMÉSIS : cinématique d'ouverture de la phase 7 — gèle TOUT le combat
        # (déplacement, attaques, transitions). Elle s'auto-clôt à la fin.
        if self.nemesis_active:
            self._update_nemesis(player, beams, projectiles, rings, telegraphs, particles)
            self.float_offset = math.sin(self.bob_t) * 14
            return
        # COURROUX : cinématique d'attaque de la phase 4 — gèle aussi tout le combat.
        if self.courroux_active:
            self._update_courroux(player, beams, projectiles, rings, telegraphs, particles)
            self.float_offset = math.sin(self.bob_t) * 14
            return
        # FINALE (la vraie fin) : pendant la SURVIE, Aegis tire son baroud ; les
        # autres actes (cinématiques) sont pilotés côté Game.
        if self.finale_active:
            if self.finale_act == "survival":
                self._finale_fire(player, projectiles, rings, telegraphs, particles)
            self.float_offset = math.sin(self.bob_t) * 14
            return
        # La corruption du décor s'estompe toute seule, même hors phase active.
        for _pf in getattr(self.game, "platforms", ()):
            if getattr(_pf, "corrupt_t", 0) > 0:
                _pf.tick()
        if self.dead:
            self.death_t += 1
            return
        if self.hit_flash > 0: self.hit_flash -= 1
        if self.invuln_t > 0: self.invuln_t -= 1
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
            else:
                self._update_phase(player, beams, projectiles, rings, telegraphs, particles)
        elif self.state == "transition":
            self._update_transition(player, beams, projectiles, rings, telegraphs, particles)
            # Dès qu'Aegis bascule en PHASE 7, NÉMÉSIS prend la main (une fois).
            if self.phase == 7 and not self.nemesis_fired:
                self._start_nemesis(player, beams, projectiles, rings, telegraphs, particles)
            # Dès qu'Aegis bascule en PHASE 4, COURROUX se déchaîne (une fois).
            if self.phase == 4 and not self.courroux_fired:
                self._start_courroux(player, beams, projectiles, rings, telegraphs, particles)

        self.float_offset = math.sin(self.bob_t) * 14

    def _compute_target_phase(self):
        frac = self.hp / self.max_hp_total
        for p in (7, 6, 5, 4, 3, 2):
            if frac <= AEGIS_PHASE_THRESHOLDS[p]:
                return max(p, self.phase)
        return max(1, self.phase)

    def _update_intro(self, player, beams, telegraphs, particles):
        """Entrée GRANDIOSE (15 s) : descente théâtrale → éveil → titre → verdict."""
        self.intro_t += 1
        t = self.intro_t
        if t < 150:                                   # suspens : tapi dans les cieux
            self.x = self.target_x; self.y = -240
            if t % 8 == 0:
                burst(particles, self.cx + random.randint(-220, 220), 70,
                      3, _AEGIS_COL_VOID, 2.0, 40, 0.0, 3)
        elif t < 430:                                 # DESCENTE lente et lourde
            u = (t - 150) / 280.0
            ue = 1 - (1 - u) ** 3
            self.y = -240 + (self.target_y - (-240)) * ue
            self.x = self.target_x
            if t % 4 == 0:
                burst(particles, self.x, self.y + self.vis * 0.5,
                      4, _AEGIS_COL_LIGHT, 3.0, 32, 0.04, 3)
        else:
            self.y = self.target_y
        # ÉVEIL : il se pose, déploie son halo (flash + secousse + déflagration).
        if t == 430:
            self.game.add_shake(18, 28)
            self.game.flash((255, 255, 255), 18)
            burst(particles, self.x, self.y, 140, _AEGIS_COL_DARK, 9.5, 64, 0.0, 7)
            burst(particles, self.x, self.y, 80, _AEGIS_COL_LIGHT, 6.0, 50, 0.0, 5)
        # NOM DE PHASE claqué une fois le dieu révélé.
        if t == 560:
            self.game.announce_phase(AEGIS_PHASE_NAMES[1])
        # (Les répliques du dieu sont dessinées, lisibles, dans _draw_aegis_intro.)
        if t == 850:
            self.game.add_shake(12, 18)
            burst(particles, self.x, self.y, 60, _AEGIS_COL_MIXED, 7.0, 46, 0.0, 5)
        # FIN → le combat commence enfin.
        if t >= 900:
            self.state = "fighting"
            self.attack_timer = 70
            self.step = 0

    # Sous-titres lore par phase entrante
    _TRANS_SUBTITLE = {
        2: "Le vernis se craquelle…",
        3: "Le masque se fissure.",
        4: "Assez de comédie. Voici mon vrai visage.",
        5: "J'ai dévoré des dieux pour ça.",
        6: "Je ne te laisserai pas partir.",
        7: "Il n'y a plus rien. Que le Néant.",
    }
    _TRANS_MILESTONE = (4, 7)   # transitions « majeures » (révélation, finale)

    def _update_transition(self, player, beams, projectiles, rings, telegraphs, particles):
        self.transition_t += 1
        nxt = self.next_phase
        # « big » = bascule d'ACTE (4 = COURROUX, 7 = NÉMÉSIS) : la cinématique
        # correspondante prend le relais. Les paliers internes (2,3,5,6) ne sont
        # PAS annoncés : le boss n'a que 2 phases visibles, la forme morphe en
        # douceur avec les PV sans bannière intermédiaire.
        big = nxt in self._TRANS_MILESTONE
        self.invuln_t = 60 if big else 14
        change_at = 60 if big else 16          # instant de bascule de forme
        end_at = 140 if big else 28            # fin de l'animation

        # ── Étape 1 : Aegis absorbe le terrain (le danger se dissipe) ──────
        if self.transition_t == 1:
            self.game.start_slowmo(22 if big else 6)
            self.game.add_shake(13 if big else 6, 22 if big else 12)
            for p in projectiles:
                burst(particles, p.x, p.y, 2, self._form_color(), 3.0, 26, 0.0, 3)
            for r in rings:
                burst(particles, r.x, r.y, 3, self._form_color(), 3.0, 26, 0.0, 3)
            projectiles[:] = []; beams[:] = []; rings[:] = []; telegraphs[:] = []
            self.emitter = None
            for m in self.minions:
                burst(particles, m.x, m.y, 6, self._form_color(), 3.0, 26, 0.0, 3)
            self.lasers = []; self.minions = []
            burst(particles, self.x, self.y, 50 if big else 26, self._form_color(), 7.5, 48, 0.0, 5)

        # ── Étape 1b : aspiration continue (uniquement pour les bascules d'acte) ──
        if big and self.transition_t < change_at and self.transition_t % 3 == 0:
            for _ in range(6):
                a = random.uniform(0, math.tau)
                d = random.uniform(140, 320)
                burst(particles, self.x + math.cos(a) * d, self.y + math.sin(a) * d,
                      1, self._form_color(), 1.0, 18, 0.0, 3)

        # ── Étape 2 : bascule de forme ─────────────────────────────────────
        if self.transition_t == change_at:
            self.phase = nxt
            # AUCUNE annonce/sous-titre ici : seules COURROUX & NÉMÉSIS (qui
            # s'enchaînent juste après pour les bascules d'acte) affichent du texte.
            if big:
                self.game.flash((255, 255, 255), 26)
                self.game.add_shake(26, 42)
                self.game.start_slowmo(18)
                for _ in range(60):
                    a = random.uniform(0, math.tau); sp = random.uniform(6, 13)
                    particles.append(Particle(
                        self.x, self.y, math.cos(a) * sp, math.sin(a) * sp,
                        random.randint(30, 60),
                        _AEGIS_COL_DARK2 if self.phase >= 4 else _AEGIS_COL_LIGHT,
                        5, 0.0))
                burst(particles, self.x, self.y, 70, self._form_color(), 9.5, 58, 0.0, 6)
            else:
                # Palier interne : morph DISCRET de la forme, sans interruption marquée.
                self.game.flash(self._form_color(), 8)
                burst(particles, self.x, self.y, 34, self._form_color(), 7.0, 46, 0.0, 5)

        # ── Étape 3 : reprise du combat ────────────────────────────────────
        if self.transition_t >= end_at:
            self.state = "fighting"
            self.attack_timer = 55 if big else 24
            self.step = 0
            self.invuln_t = 0

    # ── NÉMÉSIS : cinématique d'ouverture de la PHASE 7 ────────────────────
    def _nem_beats(self):
        """Beats (frames @60fps) de NÉMÉSIS — partagés logique/rendu pour rester
        synchro. Ordre : EYES, GRAB, LIFT, BLACK, WHITE, FACE, TAUNT, CHARGE,
        LASER, SLAM, EXHAUST, CONVERGE, BOOM (total 3000 = 50 s)."""
        return (120, 300, 480, 720, 960, 1140, 1260, 1410, 1560, 1980, 2580, 2700, 2880)

    def _start_nemesis(self, player, beams, projectiles, rings, telegraphs, particles):
        """Arme la cinématique NÉMÉSIS : 50 s scriptées, 100 % non-interactives."""
        self.nemesis_active = True
        self.nemesis_fired = True
        self.nemesis_t = 0
        self._nem_hp_set = False
        self._nem_spikes = []
        self._nem_slabs = []
        self._nem_impact_t = -999
        self._nem_impact_xy = (0.0, 0.0)
        self._nem_recoil = (0.0, 0.0)
        # Écran vidé : la cinématique démarre sur un terrain propre.
        projectiles[:] = []; beams[:] = []; rings[:] = []; telegraphs[:] = []
        self.emitter = None; self.lasers = []; self.minions = []
        # Aegis se campe au centre haut de l'arène.
        self.x = self.cx; self.y = self.target_y
        # Ancrage : position sol du héros (point de départ de la lévitation).
        self._nem_gx = float(player.rect.centerx)
        self._nem_gy = float(player.rect.centery)
        self._nem_px = self._nem_gx
        self._nem_py = self._nem_gy
        player.on_ground = False
        # Trajectoire du PANTIN (ACT IV, façon Sans) : (t_abs, x, y, kind).
        #   'floor' = écrasé au SOL → pics jaillissent du sol (uniquement là).
        #   'slab'  = fracassé contre une PLATEFORME conjurée par Aegis.
        B_SLAM = self._nem_beats()[9]
        FY = 590                                  # centre du héros à l'impact sol
        self._nem_slam_pts = [
            (B_SLAM + 0,   self.cx,  self.target_y + 215, None),
            (B_SLAM + 60,  520,  FY,  'floor'),
            (B_SLAM + 115, 980,  300, 'slab'),
            (B_SLAM + 170, 760,  FY,  'floor'),
            (B_SLAM + 225, 300,  280, 'slab'),
            (B_SLAM + 280, 620,  FY,  'floor'),
            (B_SLAM + 335, 1000, 470, 'slab'),
            (B_SLAM + 390, 440,  FY,  'floor'),
            (B_SLAM + 445, 740,  240, 'slab'),
            (B_SLAM + 500, 560,  FY,  'floor'),
            (B_SLAM + 555, 640,  FY,  'floor'),  # dernier — épuisé
        ]
        # Caméra FIGÉE et recentrée (le zoom de la cinématique prend le relais).
        self.game.cam[0] = 0.0; self.game.cam[1] = 0.0
        self.game.shake = 0; self.game.shake_strength = 0
        self.game.slowmo = 0          # pas de slow-mo : la séquence doit tenir 50 s
        self.game.flash((255, 255, 255), 18)
        self.game.set_subtitle("", 1)
        if hasattr(self.game, "set_attack_callout"):
            self.game.set_attack_callout("", 1)
        burst(particles, self.x, self.y, 70, _AEGIS_COL_DARK, 8.0, 50, 0.0, 6)

    def _nem_slam_pos(self, t, particles):
        """ACT IV — LE PANTIN (façon Sans) : projection BRUTALE. Pics au SOL
        uniquement ; plateformes conjurées comme surfaces d'impact ailleurs."""
        pts = self._nem_slam_pts
        # Segment courant.
        seg = len(pts) - 2
        if t < pts[-1][0]:
            for i in range(len(pts) - 1):
                if pts[i][0] <= t <= pts[i + 1][0]:
                    seg = i; break
        t0, x0, y0, _k0 = pts[seg]
        t1, x1, y1, k1 = pts[seg + 1]
        # Conjuration de la plateforme dès le début du segment qui y mène.
        if k1 == 'slab' and t == t0 + 1:
            self._nem_slabs.append([float(x1), float(y1), 192.0, 34.0, t, -1])
        # Approche en ACCÉLÉRATION (ease-in quadratique) → percute sec.
        if t >= pts[-1][0]:
            self._nem_px, self._nem_py = float(x1), float(y1)
        else:
            u = (t - t0) / float(max(1, t1 - t0))
            ue = u * u                     # vif à l'impact (≠ décélération)
            self._nem_px = x0 + (x1 - x0) * ue
            self._nem_py = y0 + (y1 - y0) * ue
        # Rebond sec après impact (décroît sur ~9 frames) → ça cogne.
        si = t - self._nem_impact_t
        if 0 <= si < 9:
            mag = 24 * (1 - si / 9.0)
            self._nem_px += self._nem_recoil[0] * mag
            self._nem_py += self._nem_recoil[1] * mag
        # IMPACT : pile à l'arrivée d'un waypoint (≠ point de départ).
        for k in range(1, len(pts)):
            ti, xi, yi, ki = pts[k]
            if t == ti:
                self._nem_impact_t = t
                self._nem_impact_xy = (xi, yi)
                ax = xi - pts[k - 1][1]; ay = yi - pts[k - 1][2]
                d = math.hypot(ax, ay) or 1.0
                self._nem_recoil = (-ax / d, -ay / d)   # rebond = inverse de l'approche
                if ki == 'floor':
                    # PICS uniquement depuis le SOL (pointent vers le haut).
                    for s in range(random.randint(4, 6)):
                        spread = (s - 2.5) * 30 + random.randint(-10, 10)
                        self._nem_spikes.append(
                            [xi + spread, 636.0, -90, random.randint(80, 132), t])
                else:
                    # marque la plateforme conjurée comme FRACASSÉE.
                    for sl in self._nem_slabs:
                        if abs(sl[0] - xi) < 36 and abs(sl[1] - yi) < 36:
                            sl[5] = t
                burst(particles, int(xi), int(yi), 56, _AEGIS_COL_DARK, 11.5, 46, 0.18, 7)
                burst(particles, int(xi), int(yi), 34, (255, 235, 250), 8.0, 32, 0.12, 5)
                break

    def _update_nemesis(self, player, beams, projectiles, rings, telegraphs, particles):
        """Fait avancer NÉMÉSIS : gèle/anime le héros, scripte les temps forts."""
        t = self.nemesis_t
        # Terrain maintenu absolument propre durant toute la séquence.
        if projectiles: projectiles[:] = []
        if beams: beams[:] = []
        if rings: rings[:] = []
        if telegraphs: telegraphs[:] = []
        # Aegis ancré au centre haut.
        self._drift_to(self.cx, self.target_y, 6.0)

        (B_EYES, B_GRAB, B_LIFT, B_BLACK, B_WHITE, B_FACE, B_TAUNT,
         B_CHARGE, B_LASER, B_SLAM, B_EXHAUST, B_CONVERGE, B_BOOM) = self._nem_beats()

        def _ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)   # smootherstep quintique

        # ── Position du héros, acte par acte ──
        hold_x, hold_y = self.cx, self.target_y + 215
        jx = jy = 0
        player.on_ground = False
        if t <= B_GRAB:                                   # au sol, puis poigne
            shiver = random.randint(-2, 2) if t > B_GRAB - 40 else 0
            self._nem_px = self._nem_gx + shiver
            self._nem_py = self._nem_gy
            player.on_ground = t <= B_GRAB - 40
        elif t <= B_LIFT:                                 # ARRACHAGE en arc
            u = _ease((t - B_GRAB) / float(B_LIFT - B_GRAB))
            self._nem_px = self._nem_gx + (hold_x - self._nem_gx) * u
            arc = math.sin(min(1.0, u * 1.15) * math.pi) * 55
            self._nem_py = self._nem_gy + (hold_y - self._nem_gy) * u - arc
        elif t <= B_CHARGE:                               # suspension (vides, taunt)
            self._nem_px = hold_x
            self._nem_py = hold_y + math.sin((t - B_LIFT) * 0.05) * 7
        elif t <= B_LASER:                                # charge des lasers
            self._nem_px = hold_x
            self._nem_py = hold_y + math.sin((t - B_LIFT) * 0.05) * 7
            amp = int(1 + 4 * (t - B_CHARGE) / float(B_LASER - B_CHARGE))
            jx = random.randint(-amp, amp); jy = random.randint(-amp, amp)
        elif t <= B_SLAM:                                 # ACT III — LE DÉLUGE
            self._nem_px = hold_x
            self._nem_py = hold_y + math.sin((t - B_LIFT) * 0.05) * 6
            jx = random.randint(-8, 8); jy = random.randint(-7, 7)
        elif t <= B_EXHAUST:                              # ACT IV — LE PANTIN
            self._nem_slam_pos(t, particles)
            jx = random.randint(-2, 2); jy = random.randint(-2, 2)
        elif t <= B_CONVERGE:                             # ramené au centre, épuisé
            u = _ease((t - B_EXHAUST) / float(B_CONVERGE - B_EXHAUST))
            fx0, fy0 = self._nem_slam_pts[-1][1], self._nem_slam_pts[-1][2]
            self._nem_px = fx0 + (hold_x - fx0) * u
            self._nem_py = fy0 + (hold_y - fy0) * u
            jy = int(2 * math.sin(t * 0.2))
        else:                                             # broyage final au centre
            self._nem_px = hold_x; self._nem_py = hold_y
            jx = random.randint(-9, 9); jy = random.randint(-8, 8)

        player.rect.center = (int(self._nem_px) + jx, int(self._nem_py) + jy)
        player.vx = 0.0; player.vy = 0.0
        player.invuln = max(player.invuln, 12)

        # Énergie rassemblée dans les mains d'Aegis (offsets ∝ taille du sprite).
        if B_EYES < t <= B_GRAB and t % 2 == 0:
            hox = self.vis * 0.58; hoy = self.vis * 0.47
            for sgn in (-1, 1):
                hx = self.cx + sgn * hox; hy = self.target_y + hoy
                a = random.uniform(0, math.tau); d = random.uniform(20, 80)
                particles.append(Particle(
                    hx + math.cos(a) * d, hy + math.sin(a) * d,
                    -math.cos(a) * 1.8, -math.sin(a) * 1.8,
                    random.randint(12, 22), _AEGIS_COL_DARK2, 3, 0.0))

        # Les deux trous aspirent la lumière (jusqu'à la convergence).
        if B_LIFT < t < B_CONVERGE and t % 3 == 0:
            for hx in (self.cx + 520, self.cx - 520):
                a = random.uniform(0, math.tau); d = random.uniform(50, 150)
                col = (250, 250, 255) if hx < self.cx else (70, 18, 80)
                particles.append(Particle(
                    hx + math.cos(a) * d, self.target_y + 40 + math.sin(a) * d,
                    -math.cos(a) * 2.4, -math.sin(a) * 2.4,
                    random.randint(18, 36), col, 4, 0.0))

        # Charge des lasers : étincelles aspirées vers le héros.
        if B_CHARGE < t <= B_LASER and t % 2 == 0:
            for i in range(4):
                a = i * math.tau / 4 + 0.4
                sx = self._nem_px + math.cos(a) * 360
                sy = self._nem_py + math.sin(a) * 360
                particles.append(Particle(
                    sx, sy, (self._nem_px - sx) * 0.05, (self._nem_py - sy) * 0.05,
                    random.randint(10, 18), (255, 120, 220), 3, 0.0))

        # Éclats sur le héros pendant le SPAM de lasers.
        if B_LASER < t <= B_SLAM and t % 2 == 0:
            burst(particles, int(self._nem_px), int(self._nem_py), 3,
                  _AEGIS_COL_DARK2, 4.0, 16, 0.05, 3)

        # DÉTONATION : collision des trous → ÉNORME explosion, héros à 1 PV.
        if t == B_BOOM:
            player.hp = 1
            self._nem_hp_set = True
            self.game.flash((255, 255, 255), 30)
            cx, cy = int(self._nem_px), int(self._nem_py)
            burst(particles, cx, cy, 200, (255, 255, 255), 15.0, 72, 0.0, 8)
            burst(particles, cx, cy, 120, _AEGIS_COL_DARK, 12.0, 62, 0.0, 6)
            burst(particles, cx, cy, 80, (40, 10, 60), 9.0, 56, 0.0, 6)

        self.nemesis_t += 1
        if self.nemesis_t >= self.nemesis_dur:
            # FIN : la PHASE 7 commence enfin, héros à 1 PV.
            self.nemesis_active = False
            self.phase = 7; self.next_phase = 7
            self.state = "fighting"
            self.attack_timer = 75
            self.invuln_t = 0
            self.emitter = None
            self._nem_spikes = []; self._nem_slabs = []  # nettoyage des FX scriptés
            if not self._nem_hp_set:
                player.hp = 1
            player.invuln = max(player.invuln, 100)   # court répit à la reprise
            player.rect.midbottom = (self.cx, 600)
            player.vx = 0.0; player.vy = 0.0
            self.game.announce_phase(AEGIS_PHASE_NAMES[7])

    # ── COURROUX : cinématique d'attaque de la PHASE 4 (50 s, scriptée) ─────
    def _cx_beats(self):
        """Beats (frames @60fps) partagés logique/rendu. Ordre :
        SHATTER, ROAR, PRESSURE, STORM, RAISE, SLAM, VERDICT (total 3000 = 50 s)."""
        return (300, 420, 540, 1200, 2040, 2400, 2640)

    def _start_courroux(self, player, beams, projectiles, rings, telegraphs, particles):
        """Arme COURROUX : la rage de la phase 4, 50 s 100 % non-interactives."""
        self.courroux_active = True
        self.courroux_fired = True
        self.courroux_t = 0
        self._cx_hp_set = False
        self._cx_impact_t = -999
        self._cx_impact_amp = 0.0
        self._cx_meteors = []
        projectiles[:] = []; beams[:] = []; rings[:] = []; telegraphs[:] = []
        self.emitter = None; self.lasers = []; self.minions = []
        self.x = self.cx; self.y = self.target_y
        self._cx_gx = float(player.rect.centerx)
        self._cx_gy = float(player.rect.centery)
        self.game.cam[0] = 0.0; self.game.cam[1] = 0.0
        self.game.shake = 0; self.game.shake_strength = 0
        self.game.slowmo = 0
        self.game.flash((255, 255, 255), 14)
        self.game.set_subtitle("", 1)
        if hasattr(self.game, "set_attack_callout"):
            self.game.set_attack_callout("", 1)
        burst(particles, self.x, self.y, 70, _AEGIS_COL_LIGHT, 7.0, 50, 0.0, 5)

    def _update_courroux(self, player, beams, projectiles, rings, telegraphs, particles):
        """Scripte COURROUX : rupture du masque → pression → déluge → écrasement."""
        t = self.courroux_t
        if projectiles: projectiles[:] = []
        if beams: beams[:] = []
        if rings: rings[:] = []
        if telegraphs: telegraphs[:] = []
        self._drift_to(self.cx, self.target_y, 5.0)
        (B_SHATTER, B_ROAR, B_PRESSURE, B_STORM, B_RAISE, B_SLAM, B_VERDICT) = self._cx_beats()
        floor_y = 632

        def _ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)

        # Héros TRAÎNÉ DE FORCE au centre par la pression (acte II), puis cloué là.
        gx, gy = self._cx_gx, self._cx_gy
        ctr_x, ctr_y = self.cx, 582
        if t < B_PRESSURE:
            hx, hy, amp = gx, gy, 1
        elif t < B_STORM:
            u = _ease((t - B_PRESSURE) / float(B_STORM - B_PRESSURE))
            hx = gx + (ctr_x - gx) * u
            hy = gy + (ctr_y - gy) * u
            amp = 2
        elif t < B_RAISE:
            hx, hy, amp = ctr_x, ctr_y, 4
        elif t < B_SLAM:
            hx, hy, amp = ctr_x, ctr_y, 2
        else:
            hx, hy, amp = ctr_x, ctr_y, 6
        player.rect.center = (int(hx) + random.randint(-amp, amp),
                              int(hy) + random.randint(-amp, amp))
        player.vx = 0.0; player.vy = 0.0
        player.invuln = max(player.invuln, 12)

        # ── ACT I : RUPTURE du masque + RUGISSEMENT ──
        if t == B_SHATTER:
            self._cx_impact_t = t; self._cx_impact_amp = 22
            self.game.flash((255, 240, 220), 16)
            burst(particles, self.x, self.y - self.vis * 0.3, 90, _AEGIS_COL_LIGHT, 10.0, 55, 0.12, 6)
            burst(particles, self.x, self.y - self.vis * 0.3, 50, (255, 255, 255), 7.0, 45, 0.10, 5)
        if t == B_ROAR:
            self._cx_impact_t = t; self._cx_impact_amp = 27
            self.game.flash((255, 60, 40), 14)
            burst(particles, self.x, self.y, 90, _AEGIS_COL_DARK, 9.5, 56, 0.0, 6)

        # ── ACT II : PRESSION — débris arrachés du sol, aspirés vers Aegis ──
        if B_PRESSURE <= t < B_STORM and t % 3 == 0:
            ang = random.uniform(0, math.tau); d = random.uniform(260, 540)
            dx = self.x + math.cos(ang) * d
            dy = self.target_y + 140 + abs(math.sin(ang)) * 200
            particles.append(Particle(dx, dy, (self.x - dx) * 0.018, (self.y - dy) * 0.02,
                                      random.randint(30, 55), _AEGIS_COL_VOID, 4, 0.0))

        # ── ACT III : LA MÉTÉORITE — un astre colossal se forge haut dans le ciel ──
        if B_STORM <= t < B_RAISE and t % 2 == 0:
            ang = random.uniform(0, math.tau); d = random.uniform(220, 660)
            sx = self.cx + math.cos(ang) * d; sy = 150 + math.sin(ang) * d * 0.45
            particles.append(Particle(sx, sy, (self.cx - sx) * 0.045, (150 - sy) * 0.045,
                                      random.randint(14, 28), (255, 120, 60), 4, 0.0))

        # ── ACT IV : il ABAT la météorite sur le héros (centre) ──
        if B_RAISE <= t < B_SLAM:
            u = _ease((t - B_RAISE) / float(B_SLAM - B_RAISE))
            my = 150 + (floor_y - 150) * (u * u)          # chute accélérée
            if t % 2 == 0:
                burst(particles, self.cx + random.randint(-26, 26), int(my),
                      6, (255, 120, 55), 3.5, 22, 0.0, 4)  # traînée de feu
        if t == B_SLAM:
            self._cx_impact_t = t; self._cx_impact_amp = 50
            self.game.flash((255, 255, 255), 32)
            burst(particles, self.cx, floor_y, 220, (255, 255, 255), 16.0, 78, 0.0, 8)
            burst(particles, self.cx, floor_y, 150, (255, 120, 55), 12.5, 66, 0.0, 7)
            burst(particles, self.cx, floor_y, 90, _AEGIS_COL_DARK, 11.0, 60, 0.0, 6)
            # Frappe BRUTALE mais survivable (jamais létale) — la météorite l'écrase.
            player.hp = max(1, player.hp - max(2, player.max_hp // 2))
            self._cx_hp_set = True

        self.courroux_t += 1
        if self.courroux_t >= self.courroux_dur:
            # Reprise EN DOUCEUR (pas de bascule brutale en combat) : ralenti bref,
            # long répit avant la 1re attaque, et longue invuln pour souffler.
            self.courroux_active = False
            self.phase = 4; self.next_phase = 4
            self.state = "fighting"
            self.attack_timer = 150        # ~2.5 s avant qu'il ne réattaque
            self.invuln_t = 60
            self.emitter = None
            self._cx_meteors = []
            self.game.start_slowmo(40)     # rentrée au ralenti → fondu vers le combat
            player.invuln = max(player.invuln, 150)
            player.vx = 0.0; player.vy = 0.0
            self.game.announce_phase(AEGIS_PHASE_NAMES[4])

    # ── FINALE : LA VRAIE FIN DU JEU ────────────────────────────────────────
    def _start_finale(self, player, beams, projectiles, rings, telegraphs, particles):
        """Aegis refuse de finir : il ressurgit dans le NÉANT (après sa mort ph.7)."""
        self.finale_active = True
        self.finale_fired = True
        self.finale_act = "prelude"
        self.finale_t = 0
        self.game._play_music("final_cinematic.mp3", fadein_ms=2500)   # thème de la vraie fin
        self.finale_fire_t = 0
        self._fin_cut = False
        self._fin_revealed = False
        player._void_form = False; player._void_u = 0.0
        self.dead = False; self.death_t = 0
        self.phase = 7; self.next_phase = 7
        self.state = "fighting"
        self.invuln_t = 0
        self.emitter = None; self.lasers = []; self.minions = []
        projectiles[:] = []; beams[:] = []; rings[:] = []; telegraphs[:] = []
        # LE NÉANT : une dalle noire + deux parois pour contenir le héros.
        self.game.platforms = [
            Platform(220, 560, 840, 80),
            Platform(140, -120, 80, 940),
            Platform(1060, -120, 80, 940),
        ]
        self.game.heal_orbs = []
        self.x = float(self.cx); self.y = 255.0
        self.target_x = self.cx; self.target_y = 255
        self.game.cam[0] = 0.0; self.game.cam[1] = 0.0
        self.game.shake = 0; self.game.shake_strength = 0
        self.game.slowmo = 0
        self.game.finale_gauge = 0.0
        player.hp = player.max_hp
        player.rect.midbottom = (640, 558)
        player.vx = 0.0; player.vy = 0.0
        player.invuln = max(player.invuln, 60)

    def _finale_fire(self, player, projectiles, rings, telegraphs, particles):
        """ACTE SURVIE (épuré) : PLUIE DE MÉTÉORITES à esquiver — 100 % dodgeable,
        dmg=1. Plus simple : on bouge gauche/droite/saut pour les éviter."""
        self._drift_to(self.cx, 255, 3.0)
        self.finale_fire_t += 1
        ft = self.finale_fire_t
        rate = max(15, 30 - ft // 120)             # cadence qui s'intensifie un peu
        if ft % rate == 0:
            for _ in range(1 + (1 if ft > 420 else 0)):
                x = random.uniform(230, 1050)
                self._orb(projectiles, x, -40, math.pi / 2 + random.uniform(-0.14, 0.14),
                          random.uniform(5.2, 6.8), (255, 120, 60),
                          dmg=1, radius=random.randint(15, 21), life=260, kind="meteor")
        if ft % 6 == 0:                            # petites braises ambiance
            burst(particles, self.x, self.y, 2, _AEGIS_COL_DARK2, 2.0, 22, 0.0, 3)

    # ── Dispatch des phases ────────────────────────────────────────────────
    def _update_phase(self, player, beams, projectiles, rings, telegraphs, particles):
        # Agressivité réactive : si le joueur vient d'encaisser, on relâche la pression.
        _hp = getattr(player, "hp", None)
        if _hp is not None:
            if self._last_player_hp is not None and _hp < self._last_player_hp:
                self._dodge_streak = 0
            self._last_player_hp = _hp
        # Déplacement : flotte et poursuit le joueur ; plus le vrai visage est
        # révélé, plus Aegis devient mobile et imprévisible.
        tx = max(self.ax_left + 240, min(self.ax_right - 240, player.rect.centerx))
        spd = 1.5 + 0.5 * self.phase
        # Pendant les Lasers Horloge, Aegis s'ancre presque sur place : la
        # rotation reste lisible (et impitoyable).
        if self.emitter is not None and self.emitter.get("kind") == "lasers":
            spd *= 0.18
        ty = self.target_y + math.sin(self.bob_t * 0.7) * (20 + 4 * self.phase)
        self._drift_to(tx, ty, spd)

        # Hazards persistants (lasers rotatifs, invocations du Vide) : ils vivent
        # quelle que soit l'attaque en cours.
        self._update_lasers(player, particles)
        self._update_minions(player, projectiles, particles)
        self._update_pools(player, particles)

        # Une attaque canalisée (spirale, anneaux, balayage, lasers) est
        # prioritaire : elle tire chaque frame jusqu'à épuisement.
        if self.emitter is not None:
            self._run_emitter(player, beams, projectiles, rings, telegraphs, particles)
            return

        self.attack_timer -= 1
        if self.attack_timer > 0:
            return
        getattr(self, f"_phase{self.phase}")(
            player, beams, projectiles, rings, telegraphs, particles)
        # Difficulté accrue PHASES 4→7 (« un poquito plus dur ») : cadence resserrée.
        if self.phase >= 4:
            self.attack_timer = max(3, int(self.attack_timer * (0.92 - 0.045 * (self.phase - 4))))
        self._dyn_tempo()

    # ── Émetteur d'attaques canalisées ─────────────────────────────────────
    def _run_emitter(self, player, beams, projectiles, rings, telegraphs, particles):
        e = self.emitter
        e["t"] += 1
        k = e["kind"]

        if k == "spiral":
            self.spin += e["dspin"]
            if e["t"] % e["rate"] == 0:
                for a in range(e["arms"]):
                    ang = self.spin + a * math.tau / e["arms"]
                    self._orb(projectiles, self.x, self.y, ang, e["speed"],
                              e["color"], dmg=e["dmg"], life=e.get("life", 260))

        elif k == "dspiral":
            self.spin += e["dspin"]; self.spin2 -= e["dspin"]
            if e["t"] % e["rate"] == 0:
                for a in range(e["arms"]):
                    base = a * math.tau / e["arms"]
                    self._orb(projectiles, self.x, self.y, self.spin + base,
                              e["speed"], e["color"], dmg=e["dmg"], life=e.get("life", 260))
                    self._orb(projectiles, self.x, self.y, self.spin2 + base,
                              e["speed"], e["color2"], dmg=e["dmg"], life=e.get("life", 260))

        elif k == "rings":
            if e["t"] % e["rate"] == 0:
                off = e["wave"] * e.get("twist", 0.13)
                self._ring360(projectiles, e["count"], e["speed"], e["color"],
                              dmg=e["dmg"], offset=off, life=e.get("life", 240))
                self.game.add_shake(5, 6)
                burst(particles, self.x, self.y, 14, e["color"], 5.0, 22, 0.0, 4)
                e["wave"] += 1

        elif k == "sweep":
            # Rayon tournant fait de balles rapides : trace un arc mortel.
            self.spin += e["dspin"]
            if e["t"] % e["rate"] == 0:
                for j in range(e.get("dual", 1)):
                    ang = self.spin + j * math.pi
                    self._orb(projectiles, self.x, self.y, ang, e["speed"],
                              e["color"], dmg=e["dmg"], radius=8, life=e.get("life", 200))

        elif k == "lasers":
            # Les RotLaser tournent et collisionnent dans _update_lasers ; ici on
            # gère la mise en scène de la « puissance » : traînées + vibration.
            if e["t"] % 3 == 0:
                for L in self.lasers:
                    if L.live:
                        d = random.uniform(70, L.length * 0.7)
                        burst(particles, self.x + math.cos(L.angle) * d,
                              self.y + math.sin(L.angle) * d, 1, L.color, 1.5, 12, 0.0, 3)
            if any(L.live for L in self.lasers):
                self.game.add_shake(4, 4)

        elif k == "combo":
            # Enchaînement scripté : on déclenche chaque sous-attaque à son top.
            script = e["script"]
            while e["idx"] < len(script) and e["t"] >= script[e["idx"]][0]:
                self._combo_fire(script[e["idx"]][1], player, beams,
                                 projectiles, rings, telegraphs, particles)
                e["idx"] += 1

        if e["t"] >= e["dur"]:
            if k == "lasers":
                for L in self.lasers:
                    burst(particles, self.x, self.y, 2, L.color, 4.0, 20, 0.0, 3)
                self.lasers = []
            self.emitter = None
            self.attack_timer = e.get("recover", 40)

    # ── Sélection d'attaque « façon Sans » : imprévisible, non mémorisable ──
    def _pick(self, pool, player):
        """Choisit la prochaine attaque : aléatoire pondéré, sans répétition, et
        réactif à la position du joueur. Casse l'ordre cyclique mémorisable."""
        if self._blink_cd > 0:
            self._blink_cd -= 1
        cands = [t for t in pool
                 if not (t == "blink" and self._blink_cd > 0)
                 and not (t == "combo" and self._combo_cd > 0)]
        if not cands:
            cands = list(pool)
        dist = abs(player.rect.centerx - self.x)
        far = dist > 520; close = dist < 260
        weights = []
        for t in cands:
            w = 1.0
            if t == self._last_pick: w *= 0.10          # presque jamais deux fois de suite
            if t in self._recent:   w *= 0.45           # évite la routine récente
            if far and t in ("wall", "starfall", "rings", "collapse", "blink"):
                w *= 1.9                                 # zone le joueur qui fuit
            if close and t in ("nova", "implosion", "shotgun", "sweep", "sweep2"):
                w *= 1.9                                 # punit le corps-à-corps
            # (la rareté du blink est gérée par son cooldown, pas par un malus)
            weights.append(max(0.02, w))
        t = random.choices(cands, weights=weights, k=1)[0]
        self._last_pick = t
        self._recent.append(t)
        if len(self._recent) > 3: self._recent.pop(0)
        self._dodge_streak += 1
        self._announce(t)            # on VOIT l'attaque : bandeau + flourish
        return t

    def _dyn_tempo(self):
        """Rythme imprévisible : enchaînements éclair, d'autant plus fréquents que
        le joueur esquive longtemps sans encaisser (« tu danses bien… »)."""
        if self.emitter is not None:
            return                                       # attaque canalisée : horloge propre
        aggro = min(0.62, 0.05 * self.phase + 0.035 * self._dodge_streak
                    + (0.045 if self.phase >= 4 else 0.0))
        if self._tempo_chain > 0:
            self._tempo_chain -= 1
            self.attack_timer = max(3, int(self.attack_timer * 0.32))
        elif random.random() < aggro:
            self._tempo_chain = random.randint(1, 2)
            self.attack_timer = max(3, int(self.attack_timer * 0.32))
        if self._dodge_streak and self._dodge_streak % 7 == 0 and random.random() < 0.6:
            self.game.set_subtitle(random.choice(self._taunts), 70)

    # ── PHASE 1 : L'Ange Gardien (le masque bienveillant) ──────────────────
    def _phase1(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["shotgun", "starfall", "nova"], player)
        if c == "shotgun":
            self._atk_shotgun(player, projectiles, telegraphs, n=5, spread=0.55,
                              speed=6.0, dmg=2, color=_AEGIS_COL_LIGHT)
            self.attack_timer = 80
        elif c == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=9, dmg=2, gap=280, color=_AEGIS_COL_LIGHT)
            self.attack_timer = 95
        else:
            self._atk_nova(player, projectiles, rings, telegraphs, particles,
                           dmg=2, color=_AEGIS_COL_LIGHT)
            self.attack_timer = 100

    # ── PHASE 2 : La Fissure (la première spirale traverse le masque) ──────
    def _phase2(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["spiral", "wall", "shotgun", "starfall"], player)
        if c == "spiral":
            self.emitter = dict(kind="spiral", t=0, dur=150, rate=6, arms=2,
                                dspin=0.13, speed=4.4, color=_AEGIS_COL_LIGHT,
                                dmg=2, recover=45)
        elif c == "wall":
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=210, dmg=3)
            self.attack_timer = 85
        elif c == "shotgun":
            self._atk_shotgun(player, projectiles, telegraphs, n=7, spread=0.7,
                              speed=6.5, dmg=2, color=_AEGIS_COL_MIXED)
            self.attack_timer = 70
        else:
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=12, dmg=2, gap=240, color=_AEGIS_COL_MIXED)
            self.attack_timer = 80

    # ── PHASE 3 : Le Mensonge Exposé (double spirale inversée) ─────────────
    def _phase3(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["dspiral", "starfall", "swarm", "shotgun", "wall"], player)
        if c == "dspiral":
            self.emitter = dict(kind="dspiral", t=0, dur=170, rate=6, arms=2,
                                dspin=0.16, speed=4.8, color=_AEGIS_COL_MIXED,
                                color2=_AEGIS_COL_DARK2, dmg=2, recover=42)
        elif c == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=15, dmg=2, gap=220, color=_AEGIS_COL_MIXED)
            self.attack_timer = 72
        elif c == "swarm":
            self._atk_swarm(player, projectiles, n=4, dmg=2, homing=0.11,
                            color=_AEGIS_COL_DARK2)
            self.attack_timer = 80
        elif c == "shotgun":
            self._atk_shotgun(player, projectiles, telegraphs, n=9, spread=0.85,
                              speed=7.0, dmg=2, color=_AEGIS_COL_MIXED)
            self.attack_timer = 66
        else:
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=185, dmg=3)
            self.attack_timer = 78

    # ── PHASE 4 : Le Vide Révélé (vrai visage — enfer de balles) ───────────
    def _phase4(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["rings", "wall", "implosion", "starfall", "spiral",
                        "shotgun", "blink", "corrosion"], player)
        if c == "rings":
            self.emitter = dict(kind="rings", t=0, dur=180, rate=24, wave=0,
                                count=22, speed=4.0, twist=0.14,
                                color=_AEGIS_COL_DARK, dmg=2, recover=34)
        elif c == "wall":
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=170, dmg=3)
            self.attack_timer = 70
        elif c == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=19, dmg=2, gap=200, color=_AEGIS_COL_DARK)
            self.attack_timer = 64
        elif c == "spiral":
            self.emitter = dict(kind="spiral", t=0, dur=160, rate=5, arms=3,
                                dspin=0.18, speed=5.0, color=_AEGIS_COL_DARK,
                                dmg=2, recover=34)
        elif c == "implosion":
            self._atk_implosion(player, projectiles, telegraphs, particles,
                                count=30, speed=5.0, color=_AEGIS_COL_DARK)
            self.attack_timer = 88
        elif c == "blink":
            self._atk_blinkbeam(player, projectiles, telegraphs, particles)
        elif c == "corrosion":
            self._atk_corrosion(player, projectiles, telegraphs, particles, n=3, dmg=1)
        else:
            self._atk_shotgun(player, projectiles, telegraphs, n=9, spread=0.9,
                              speed=7.2, dmg=2, color=_AEGIS_COL_DARK2)
            self.attack_timer = 60

    # ── PHASE 5 : L'Héritage Volé (combos de pouvoirs dérobés) ─────────────
    def _phase5(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["combo_ws", "summon", "rings", "combo_rs", "implosion",
                        "shotgun", "swarm", "wall", "blink", "corrosion",
                        "combo"], player)
        if c == "combo_ws":
            # Mur à franchir PENDANT une spirale.
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=185, dmg=3, dur=80)
            self.emitter = dict(kind="spiral", t=0, dur=150, rate=6, arms=3,
                                dspin=0.17, speed=4.6, color=_AEGIS_COL_DARK,
                                dmg=2, recover=34)
        elif c == "rings":
            self.emitter = dict(kind="rings", t=0, dur=190, rate=22, wave=0,
                                count=24, speed=4.2, twist=0.16,
                                color=_AEGIS_COL_DARK, dmg=2, recover=32)
        elif c == "combo_rs":
            # Pluie d'étoiles PENDANT une double spirale.
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=16, dmg=2, gap=210, color=_AEGIS_COL_DARK2)
            self.emitter = dict(kind="dspiral", t=0, dur=150, rate=7, arms=2,
                                dspin=0.18, speed=4.8, color=_AEGIS_COL_DARK,
                                color2=_AEGIS_COL_DARK2, dmg=2, recover=32)
        elif c == "shotgun":
            self._atk_shotgun(player, projectiles, telegraphs, n=11, spread=1.0,
                              speed=7.4, dmg=2, color=_AEGIS_COL_DARK2)
            self.attack_timer = 56
        elif c == "swarm":
            self._atk_swarm(player, projectiles, n=6, dmg=2, homing=0.13,
                            color=_AEGIS_COL_DARK2)
            self.attack_timer = 66
        elif c == "summon":
            self._atk_summon(particles, n=2, orbit=210, life=520)
            self.attack_timer = 70
        elif c == "implosion":
            self._atk_implosion(player, projectiles, telegraphs, particles,
                                count=36, speed=5.2, color=_AEGIS_COL_DARK2)
            self.attack_timer = 82
        elif c == "blink":
            self._atk_blinkbeam(player, projectiles, telegraphs, particles)
        elif c == "corrosion":
            self._atk_corrosion(player, projectiles, telegraphs, particles, n=4, dmg=1)
        elif c == "combo":
            self._atk_combo(player, beams, projectiles, rings, telegraphs,
                            particles)
        else:
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=1, gap_w=200, dmg=3)
            self.attack_timer = 60

    # ── PHASE 6 : Dernier Recours (aspiration + frénésie) ──────────────────
    def _phase6(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["lasers", "summon", "sweep", "combo_ws", "implosion",
                        "rings", "dspiral", "starfall", "swarm", "blink",
                        "corrupt", "corrosion", "combo"], player)
        if c == "sweep":
            self.emitter = dict(kind="sweep", t=0, dur=170, rate=2, dual=2,
                                dspin=0.085, speed=8.0, color=_AEGIS_COL_DARK2,
                                dmg=2, recover=30)
        elif c == "combo_ws":
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=170, dmg=3, dur=72)
            self.emitter = dict(kind="spiral", t=0, dur=150, rate=5, arms=3,
                                dspin=0.2, speed=5.0, color=_AEGIS_COL_DARK,
                                dmg=2, recover=28)
        elif c == "rings":
            self.emitter = dict(kind="rings", t=0, dur=190, rate=20, wave=0,
                                count=26, speed=4.4, twist=0.17,
                                color=_AEGIS_COL_DARK, dmg=2, recover=28)
        elif c == "dspiral":
            self.emitter = dict(kind="dspiral", t=0, dur=170, rate=6, arms=3,
                                dspin=0.19, speed=5.0, color=_AEGIS_COL_DARK,
                                color2=_AEGIS_COL_DARK2, dmg=2, recover=28)
        elif c == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=22, dmg=2, gap=185, color=_AEGIS_COL_DARK)
            self.attack_timer = 52
        elif c == "lasers":
            self._cast_lasers(particles, n=2, omega=0.016, width=46, dmg=3,
                              life=300, warmup=48)
        elif c == "summon":
            self._atk_summon(particles, n=3, orbit=215, life=540)
            self.attack_timer = 62
        elif c == "implosion":
            self._atk_implosion(player, projectiles, telegraphs, particles,
                                count=42, speed=5.4, color=_AEGIS_COL_DARK)
            self.attack_timer = 72
        elif c == "blink":
            self._atk_blinkbeam(player, projectiles, telegraphs, particles)
        elif c == "corrupt":
            self._atk_corrupt_world(player, projectiles, telegraphs, particles,
                                    n=2, dur=440)
        elif c == "corrosion":
            self._atk_corrosion(player, projectiles, telegraphs, particles, n=5, dmg=1)
        elif c == "combo":
            self._atk_combo(player, beams, projectiles, rings, telegraphs,
                            particles)
        else:
            self._atk_swarm(player, projectiles, n=7, dmg=2, homing=0.14,
                            color=_AEGIS_COL_DARK2)
            self.attack_timer = 58

    # ── PHASE 7 : Le Néant Absolu (marathon final — quasi impossible) ──────
    def _phase7(self, player, beams, projectiles, rings, telegraphs, particles):
        c = self._pick(["lasers", "summon", "collapse", "implosion", "sweep2",
                        "combo_full", "rings", "starfall", "shotgun", "blink",
                        "corrupt", "corrosion", "combo"], player)
        if c == "collapse":
            # Le Néant : anneaux 360° très denses + mur simultané.
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=165, dmg=3, dur=70)
            self.emitter = dict(kind="rings", t=0, dur=200, rate=16, wave=0,
                                count=30, speed=4.6, twist=0.2,
                                color=_AEGIS_COL_DARK, dmg=2, recover=24)
        elif c == "sweep2":
            self.emitter = dict(kind="sweep", t=0, dur=190, rate=2, dual=3,
                                dspin=0.1, speed=8.5, color=_AEGIS_COL_DARK2,
                                dmg=2, recover=24)
        elif c == "combo_full":
            # Pluie d'étoiles + double spirale + nova : saturation totale.
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=20, dmg=2, gap=180, color=_AEGIS_COL_DARK2)
            self._atk_nova(player, projectiles, rings, telegraphs, particles,
                           dmg=3, color=_AEGIS_COL_DARK)
            self.emitter = dict(kind="dspiral", t=0, dur=160, rate=6, arms=3,
                                dspin=0.21, speed=5.2, color=_AEGIS_COL_DARK,
                                color2=_AEGIS_COL_DARK2, dmg=2, recover=24)
        elif c == "rings":
            self.emitter = dict(kind="rings", t=0, dur=190, rate=15, wave=0,
                                count=30, speed=4.8, twist=0.22,
                                color=_AEGIS_COL_DARK, dmg=2, recover=22)
        elif c == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=26, dmg=2, gap=165, color=_AEGIS_COL_DARK)
            self.attack_timer = 46
        elif c == "lasers":
            self._cast_lasers(particles, n=3, omega=0.020, width=50, dmg=3,
                              life=360, warmup=44)
        elif c == "summon":
            self._atk_summon(particles, n=4, orbit=220, life=560)
            self.attack_timer = 56
        elif c == "implosion":
            self._atk_implosion(player, projectiles, telegraphs, particles,
                                count=48, speed=5.6, color=_AEGIS_COL_DARK2)
            self.attack_timer = 64
        elif c == "blink":
            self._atk_blinkbeam(player, projectiles, telegraphs, particles)
        elif c == "corrupt":
            self._atk_corrupt_world(player, projectiles, telegraphs, particles,
                                    n=3, dur=480)
        elif c == "corrosion":
            self._atk_corrosion(player, projectiles, telegraphs, particles, n=6, dmg=1)
        elif c == "combo":
            self._atk_combo(player, beams, projectiles, rings, telegraphs,
                            particles)
        else:
            self._atk_shotgun(player, projectiles, telegraphs, n=13, spread=1.1,
                              speed=7.8, dmg=2, color=_AEGIS_COL_DARK2)
            self.attack_timer = 44

    # ── Briques d'attaque (basées sur les primitives globales) ─────────────
    def _orb(self, projectiles, x, y, ang, speed, color, dmg=2, radius=9,
             life=260, homing=0.0, target=None, kind="orb"):
        projectiles.append(BossProjectile(
            x, y, math.cos(ang) * speed, math.sin(ang) * speed, DIM_REAL,
            radius=radius, life=life, homing=homing, target=target,
            color=color, kind=kind, dmg=dmg, hits_any_dim=True))

    def _ring360(self, projectiles, count, speed, color, dmg=2, offset=0.0,
                 radius=9, life=240):
        for i in range(count):
            ang = offset + i * math.tau / count
            self._orb(projectiles, self.x, self.y, ang, speed, color,
                      dmg=dmg, radius=radius, life=life)

    def _atk_shotgun(self, player, projectiles, telegraphs, n, spread, speed,
                     dmg, color):
        ox, oy = self.x, self.y
        ang = math.atan2(player.rect.centery - oy, player.rect.centerx - ox)
        def fire():
            for i in range(n):
                tt = (i / (n - 1) - 0.5) if n > 1 else 0.0
                self._orb(projectiles, ox, oy, ang + tt * spread, speed, color,
                          dmg=dmg, radius=9, life=270)
        telegraphs.append(Telegraph("fan", 50, DIM_REAL, on_fire=fire, color=color,
                                    x=ox, y=oy, angle=ang, spread=spread,
                                    count=n, length=750, hits_any_dim=True))

    def _atk_starfall(self, player, projectiles, telegraphs, particles, count,
                      dmg, gap, color):
        """Pluie de comètes du Néant : des orbes plongent du ciel sur toute
        l'arène, sauf une colonne-refuge mobile. Aucun faisceau — chaque chute
        est marquée par un réticule du vide (langage propre à Aegis)."""
        left = self.ax_left; right = self.ax_right
        span = right - left
        safe = random.randint(left + gap, right - gap)
        for i in range(count):
            x = int(left + span * (i + 0.5) / count) + random.randint(-18, 18)
            if abs(x - safe) < gap:
                continue
            def fire(px=x):
                burst(particles, px, 84, 6, color, 4.0, 16, 0.06, 3)
                self._orb(projectiles, px, self.ay_top + 30, math.pi / 2, 7.8,
                          color, dmg=dmg, radius=10, life=240)
            # Tell : un réticule du vide en haut de la colonne (pas de pilier-faisceau).
            telegraphs.append(Telegraph("circle", 50, DIM_REAL, on_fire=fire,
                                        color=color, x=x, y=92, r=20,
                                        hits_any_dim=True))

    def _atk_wall(self, player, projectiles, telegraphs, particles, n_gaps=2,
                  gap_w=180, dmg=3, dur=70):
        """La Herse du Néant : une herse dense d'orbes du vide descend du ciel,
        perforée de colonnes-refuges (dont une sur le joueur). Aucun faisceau —
        uniquement des projectiles : c'est le langage propre à Aegis."""
        left = self.ax_left; right = self.ax_right
        gaps = [max(left + gap_w, min(right - gap_w, player.rect.centerx))]
        for _ in range(max(0, n_gaps - 1)):
            gaps.append(random.randint(left + gap_w, right - gap_w))
        col = _AEGIS_COL_DARK
        step = 30
        xs = [x for x in range(int(left) + 20, int(right), step)
              if not any(abs(x - g) < gap_w for g in gaps)]
        def fire(cols=tuple(xs)):
            self.game.add_shake(15, 22)
            burst(particles, self.x, self.y, 26, col, 6.5, 30, 0.0, 5)
            for cx in cols:
                self._orb(projectiles, cx, self.ay_top + 20, math.pi / 2, 3.4,
                          col, dmg=dmg, radius=12, life=320)
        # Tell : réticules du vide alignés en haut des colonnes mortelles.
        for cx in xs[::2]:
            telegraphs.append(Telegraph("circle", dur, DIM_REAL,
                                        color=col, x=cx, y=96, r=15,
                                        hits_any_dim=True))
        # Une seule télégraphe porte le déclenchement (sinon salves multiples).
        telegraphs.append(Telegraph("circle", dur, DIM_REAL, on_fire=fire,
                                    color=col, x=self.x, y=self.y, r=1,
                                    hits_any_dim=True))

    def _atk_nova(self, player, projectiles, rings, telegraphs, particles, dmg, color=None):
        """SUPERNOVA — l'étoile d'Aegis s'effondre puis DÉTONE. Deux contraintes
        simultanées : une TRIPLE onde de choc concentrique (contrainte radiale —
        il faut bouger vers/contre le centre) DOUBLÉE d'une déflagration d'orbes
        360° percée d'un ou deux couloirs étroits (contrainte angulaire — il faut
        tenir le bon angle). Aux phases hautes, un second voile tourné d'un
        demi-couloir t'oblige à TE REPLACER en pleine onde. Plus de simple anneau
        esquivable : une vraie mort stellaire."""
        col = color or self._form_color()
        cx, cy = self.x, self.y
        p = self.phase
        bullets   = 26 + 4 * p                       # densité de la déflagration
        lanes     = 2 if p >= 6 else 1               # couloirs de survie
        lane_half = 0.40 if p >= 7 else (0.46 if p >= 5 else 0.56)
        n_rings   = 3 if p >= 4 else 2               # ondes concentriques
        second    = p >= 6                           # second voile décalé
        base      = random.uniform(0, math.tau)
        def fire():
            self.game.start_slowmo(6)
            self.game.add_shake(22, 32)
            self.game.flash((255, 245, 230), 9)
            burst(particles, cx, cy, 72, col, 10.5, 56, 0.0, 6)
            burst(particles, cx, cy, 30, (255, 250, 235), 7.0, 40, 0.0, 4)
            # — triple onde de choc : rayons + vitesses échelonnés —
            for i in range(n_rings):
                rings.append(Ring(cx, cy, DIM_REAL, max_r=520 + i * 130,
                                  life=56 + i * 16, color=col, dmg=dmg,
                                  hits_any_dim=True))
            # — déflagration 360° avec couloir(s) de survie —
            gaps = [base + k * math.tau / lanes for k in range(lanes)]
            for i in range(bullets):
                a = i * math.tau / bullets
                if any(abs(((a - g + math.pi) % math.tau) - math.pi) < lane_half
                       for g in gaps):
                    continue
                self._orb(projectiles, cx, cy, a, 5.6, col, dmg=dmg,
                          radius=9, life=210)
            # — second voile décalé d'un demi-couloir : replacement forcé —
            if second:
                gaps2 = [g + math.tau / (2 * lanes) for g in gaps]
                for i in range(bullets):
                    a = i * math.tau / bullets + math.pi / bullets
                    if any(abs(((a - g + math.pi) % math.tau) - math.pi) < lane_half
                           for g in gaps2):
                        continue
                    self._orb(projectiles, cx, cy, a, 3.7, _AEGIS_COL_DARK2,
                              dmg=dmg, radius=8, life=250)
        telegraphs.append(Telegraph("collapse", 72, DIM_REAL, on_fire=fire, color=col,
                                    x=cx, y=cy, r=300, hits_any_dim=True))

    def _atk_swarm(self, player, projectiles, n, dmg, homing=0.12, color=None):
        col = color or self._form_color()
        for i in range(n):
            a = random.uniform(0, math.tau)
            self._orb(projectiles, self.x, self.y, a, 2.6, col, dmg=dmg,
                      radius=9, life=330, homing=homing, target=player)

    # ── Le Trait du Néant : blink imprévisible + trait éclair prédictif ─────
    def _atk_blinkbeam(self, player, projectiles, telegraphs, particles):
        """Aegis se dissout dans le vide et resurgit ailleurs pour transpercer le
        joueur d'un trait fulgurant — origine ET timing imprévisibles (façon Sans)."""
        px, py = player.rect.center
        # Blink : réapparition à distance moyenne, sous un angle aléatoire.
        a0 = random.uniform(0, math.tau)
        R = random.randint(360, 520)
        nx = max(self.ax_left + 130, min(self.ax_right - 130, px + math.cos(a0) * R))
        ny = max(self.ay_top + 90,  min(self.ay_bottom - 170, py + math.sin(a0) * R))
        burst(particles, self.x, self.y, 24, _AEGIS_COL_VOID, 7.0, 28, 0.0, 5)
        self.x, self.y = nx, ny
        ox, oy = self.x, self.y
        burst(particles, ox, oy, 30, _AEGIS_COL_DARK2, 7.5, 32, 0.0, 5)
        self.game.start_slowmo(6)
        self.game.add_shake(11, 12)
        self.game.flash(_AEGIS_COL_DARK2, 6)
        # Visée prédictive : on mène la cible selon sa vitesse actuelle.
        lead = 9
        tx = px + getattr(player, "vx", 0.0) * lead
        ty = py + getattr(player, "vy", 0.0) * lead
        ang = math.atan2(ty - oy, tx - ox)
        col = _AEGIS_COL_DARK2
        def fire(a=ang, sx=ox, sy=oy):
            self.game.add_shake(15, 14)
            burst(particles, sx, sy, 22, col, 8.0, 30, 0.0, 5)
            for i in range(13):                       # trait dense (lance) + léger éventail
                tt = (i / 12 - 0.5)
                self._orb(projectiles, sx, sy, a + tt * 0.12, 11.5, col,
                          dmg=3, radius=9, life=160)
        telegraphs.append(Telegraph("fan", 26, DIM_REAL, on_fire=fire, color=col,
                                    x=ox, y=oy, angle=ang, spread=0.12, count=13,
                                    length=900, hits_any_dim=True))
        self.attack_timer = 54
        self._blink_cd = random.randint(2, 4)

    # ── Lasers Horloge : l'ultime démonstration de puissance ───────────────
    def _cast_lasers(self, particles, n, omega, width, dmg, life, warmup):
        col = _AEGIS_COL_DARK2
        base = random.uniform(0, math.tau)
        # alterne le sens de rotation des aiguilles selon la phase
        sign = 1 if self.phase % 2 == 0 else -1
        for i in range(n):
            self.lasers.append(RotLaser(
                self, base + i * math.tau / n, omega * sign, length=1700,
                width=width, dmg=dmg, life=life, warmup=warmup, color=col))
        # Mise en scène : ralenti bref, secousse montante, flash, aura, déclaration.
        self.game.start_slowmo(10)
        self.game.add_shake(18, warmup)
        self.game.flash(col, 8)
        self.game.set_subtitle("Ma puissance n'a pas de limite.", 80)
        burst(particles, self.x, self.y, 70, col, 8.5, 52, 0.0, 6)
        self.emitter = dict(kind="lasers", t=0, dur=warmup + life + 16, recover=46)

    def _update_lasers(self, player, particles):
        if not self.lasers:
            return
        for L in self.lasers:
            was_live = L.live
            L.update()
            if (not was_live) and L.live and not L.went_live:
                # le faisceau s'allume : impact de puissance
                L.went_live = True
                self.game.add_shake(20, 16)
                self.game.flash(self._form_color(), 9)
                burst(particles, self.x, self.y, 26, L.color, 7.0, 34, 0.0, 5)
            if L.hits(player.rect):
                if player.hurt(L.dmg):
                    self.game.add_shake(12, 16)
                    burst(particles, player.rect.centerx, player.rect.centery,
                          24, Pal.HP_FILL, 5.0, 28, 0.15, 4)
        self.lasers[:] = [L for L in self.lasers if not L.dead]

    # ── Invocations du Vide ────────────────────────────────────────────────
    def _atk_summon(self, particles, n, orbit=210, life=480):
        need = n - len(self.minions)
        if need <= 0:
            return
        col = _AEGIS_COL_DARK2
        self.game.add_shake(8, 12)
        base = random.uniform(0, math.tau)
        for i in range(need):
            ang = base + i * math.tau / max(1, need)
            self.minions.append(VoidSpawn(self, ang, orbit + i * 12, life=life, color=col))
            burst(particles, self.x + math.cos(ang) * orbit,
                  self.y + math.sin(ang) * orbit, 18, col, 5.0, 30, 0.0, 4)

    def _update_minions(self, player, projectiles, particles):
        if not self.minions:
            return
        for m in self.minions:
            m.update(player, projectiles, particles)
        self.minions[:] = [m for m in self.minions if not m.dead]

    # ── Implosion convergente (mur de balles qui se referme) ───────────────
    def _atk_implosion(self, player, projectiles, telegraphs, particles, count,
                       speed, color, dmg=2):
        cx, cy = player.rect.center
        R = 760
        gap_ang = random.uniform(0, math.tau)
        gap_half = 0.46   # ~26° : le couloir de survie
        def fire():
            self.game.add_shake(11, 16)
            burst(particles, cx, cy, 26, color, 6.0, 30, 0.0, 4)
            for i in range(count):
                a = i * math.tau / count
                da = abs(((a - gap_ang + math.pi) % math.tau) - math.pi)
                if da < gap_half:
                    continue
                sx = cx + math.cos(a) * R
                sy = cy + math.sin(a) * R
                self._orb(projectiles, sx, sy, a + math.pi, speed, color,
                          dmg=dmg, radius=9, life=int(R / speed) + 45)
        telegraphs.append(Telegraph("ring", 64, DIM_REAL, on_fire=fire, color=color,
                                    x=cx, y=cy, r=R, hits_any_dim=True))

    # ── La Corrosion du Vide : mares acides qui rongent le sol ─────────────
    def _update_pools(self, player, particles):
        if not self.pools:
            return
        for pool in self.pools:
            pool.update(player, particles)
        self.pools[:] = [p for p in self.pools if not p.dead]

    def _atk_corrosion(self, player, projectiles, telegraphs, particles, n=4, dmg=1):
        """Aegis vomit des mares de corrosion : le sol devient un piège mortel.
        La 1re vise le joueur ; chaque impact crache une onde rasante qu'il faut
        SAUTER. Le terrain se referme — la souillure d'un dieu sous tes pieds."""
        floor_y = 600   # haut du sol de l'arène lunaire
        col = _AEGIS_COL_DARK
        span_l, span_r = self.ax_left + 140, self.ax_right - 140
        # 1re mare sur le joueur, le reste étalé pour couper le sol en morceaux
        xs = [int(max(span_l, min(span_r, player.rect.centerx)))]
        for _ in range(max(0, n - 1)):
            xs.append(random.randint(int(span_l), int(span_r)))
        shock = self.phase >= 5     # onde rasante à sauter dès la phase 5
        for fx in xs:
            def fire(fx=fx):
                self.pools.append(CorrosionPool(fx, floor_y, r=86, life=380,
                                                dmg=dmg, color=col))
                burst(particles, fx, floor_y, 34, col, 6.5, 36, -0.14, 6)
                self.game.add_shake(9, 14)
                if shock:
                    for ang in (0.0, math.pi):     # onde rasante gauche + droite
                        self._orb(projectiles, fx, floor_y - 18, ang, 7.2, col,
                                  dmg=dmg + 1, radius=11, life=115)
            telegraphs.append(Telegraph("circle", 50, DIM_REAL, on_fire=fire,
                                        color=col, x=fx, y=floor_y, r=86,
                                        hits_any_dim=True))
        self.attack_timer = 78

    # ── La Corruption du Monde : Aegis dévore le décor ─────────────────────
    def _atk_corrupt_world(self, player, projectiles, telegraphs, particles,
                           n=2, dur=460):
        """Aegis dévore le décor : les plateformes corrompues s'effondrent sous
        toi et EXPLOSENT en éclats du Vide. Il vise d'abord le sol sous tes pieds
        — un dieu réécrit le monde et ne te laisse plus où te poser."""
        all_p = [p for p in getattr(self.game, "platforms", ())
                 if p.rect.height < 60 and p.rect.width < 400 and not p.corrupted]
        if not all_p:
            self.attack_timer = 48
            return
        # Priorité : la plateforme la plus proche du joueur (le forcer à fuir).
        px, py = player.rect.centerx, player.rect.centery
        all_p.sort(key=lambda p: (p.rect.centerx - px) ** 2
                                 + (p.rect.centery - py) ** 2)
        chosen = [all_p[0]]
        rest = all_p[1:]
        random.shuffle(rest)
        chosen += rest[:max(0, n - 1)]
        self.game.add_shake(12, 20)
        col = _AEGIS_COL_VOID
        for p in chosen:
            cxp, cyp = p.rect.centerx, p.rect.centery
            def fire(pl=p, fx=cxp, fy=cyp):
                pl.corrupt(dur)
                self.game.add_shake(16, 24)
                self.game.flash(_AEGIS_COL_DARK2, 5)
                burst(particles, fx, fy, 50, col, 8.0, 48, -0.03, 7)
                burst(particles, fx, fy, 30, _AEGIS_COL_DARK2, 6.5, 36, 0.0, 5)
                # Éruption d'éclats du Vide vers le haut : on ne campe pas dessus.
                for k in range(11):
                    a = -math.pi + k * math.pi / 10
                    self._orb(projectiles, fx, fy, a, random.uniform(4.0, 6.5),
                              _AEGIS_COL_DARK, dmg=2, radius=9, life=150)
                # Posé dessus à l'instant fatal = brûlure du Néant.
                if player.rect.bottom <= pl.rect.top + 18 and \
                   pl.rect.left - 14 < player.rect.centerx < pl.rect.right + 14:
                    player.hurt(2)
            telegraphs.append(Telegraph("circle", 66, DIM_REAL, on_fire=fire,
                                        color=col, x=cxp, y=cyp,
                                        r=max(50, p.rect.width // 2),
                                        hits_any_dim=True))
        self.attack_timer = 78

    # ── L'Enchaînement Divin : la CINÉMATIQUE (façon combat de Sans) ────────
    def _atk_combo(self, player, beams, projectiles, rings, telegraphs, particles):
        """L'Enchaînement Divin n'est plus une simple rafale : c'est une
        CINÉMATIQUE jouable. Le temps se fige une demi-seconde, des bandes
        letterbox se ferment, le titre claque — puis Aegis déverse vague après
        vague, sans le moindre répit, en se téléportant et en corrompant le
        monde, pour finir sur une SUPERNOVA. Le joueur garde la main et doit
        survivre au cadrage : c'est le climax du boss final."""
        self._combo_cd = 420
        # — Mise en scène d'ouverture : on FIGE, on cadre, on claque le titre. —
        self.game.start_slowmo(12)
        self.game.add_shake(18, 26)
        self.game.flash(_AEGIS_COL_DARK2, 10)
        self._cast_flourish(_AEGIS_COL_DARK2, 44)
        burst(particles, self.x, self.y, 80, _AEGIS_COL_DARK2, 9.0, 56, 0.0, 6)
        burst(particles, self.x, self.y, 40, _AEGIS_COL_DARK, 6.0, 44, 0.0, 4)
        p = self.phase
        # Scripts (frame, token). « wave » = nouvelle vague (pulse + compteur).
        if p <= 5:
            script = [(0, "wave"), (4, "shotgun"), (40, "starfall"),
                      (78, "wave"), (82, "swarm"), (116, "implosion"),
                      (158, "wave"), (162, "shotgun"), (198, "nova")]
            dur = 268
        elif p == 6:
            script = [(0, "wave"), (4, "wall"), (36, "starfall"), (70, "shotgun"),
                      (104, "wave"), (108, "swarm"), (140, "corrosion"),
                      (176, "implosion"),
                      (214, "wave"), (218, "blink"), (250, "nova")]
            dur = 320
        else:
            script = [(0, "wave"), (4, "wall"), (30, "starfall"), (60, "shotgun"),
                      (92, "wave"), (96, "corrosion"), (124, "swarm"),
                      (152, "implosion"),
                      (186, "wave"), (190, "corrupt"), (222, "blink"),
                      (252, "shotgun"),
                      (286, "wave"), (290, "nova")]
            dur = 364
        waves = sum(1 for f, tok in script if tok == "wave")
        # — Arme la cinématique : bandes + titre + compteur de vagues. —
        self._cine_active = True
        self._cine_t = 0
        self._cine_dur = dur + 64          # marge pour la sortie des bandes
        self._cine_name = self._SPECIALS["combo"]
        self._cine_wave = 0
        self._cine_waves = waves
        self.emitter = dict(kind="combo", t=0, dur=dur, idx=0, recover=48,
                            script=script)

    def _combo_fire(self, tok, player, beams, projectiles, rings, telegraphs, particles):
        col, col2 = _AEGIS_COL_DARK, _AEGIS_COL_DARK2
        if tok == "wave":
            # Nouvelle vague : pulse dramatique + avance le compteur du letterbox.
            self._cine_wave = min(self._cine_waves, self._cine_wave + 1)
            self.game.flash(col2, 6)
            self.game.add_shake(12, 14)
            self._cast_flourish(col2, 20)
            burst(particles, self.x, self.y, 30, col2, 7.8, 38, 0.0, 5)
            return
        if tok == "starfall":
            self._atk_starfall(player, projectiles, telegraphs, particles,
                               count=13 + self.phase, dmg=2, gap=200, color=col)
        elif tok == "shotgun":
            self._atk_shotgun(player, projectiles, telegraphs, n=9 + self.phase // 2,
                              spread=0.98, speed=7.3, dmg=2, color=col2)
        elif tok == "implosion":
            self._atk_implosion(player, projectiles, telegraphs, particles,
                                count=30 + 3 * self.phase, speed=5.2, color=col)
        elif tok == "nova":
            self._atk_nova(player, projectiles, rings, telegraphs, particles,
                           dmg=3, color=col2)
        elif tok == "wall":
            self._atk_wall(player, projectiles, telegraphs, particles,
                           n_gaps=2, gap_w=175, dmg=3, dur=66)
        elif tok == "swarm":
            self._atk_swarm(player, projectiles, n=5 + self.phase // 2, dmg=2,
                            homing=0.13, color=col2)
        elif tok == "corrosion":
            self._atk_corrosion(player, projectiles, telegraphs, particles,
                                n=3, dmg=1)
        elif tok == "corrupt":
            self._atk_corrupt_world(player, projectiles, telegraphs, particles,
                                    n=2, dur=420)
        elif tok == "blink":
            # Aegis se téléporte EN PLEINE cinématique : cadrage dynamique.
            self._atk_blinkbeam(player, projectiles, telegraphs, particles)
        self.game.add_shake(7, 9)
        self._cast_flourish(col2, 13)     # pulsation visible à chaque maillon

    # ── Annonce + flourish : « VOIR » les attaques spéciales ───────────────
    _SPECIALS = {
        "shotgun":   "SALVE DIVINE",
        "starfall":  "PLUIE DE COMÈTES",
        "wall":      "LA HERSE DU NÉANT",
        "nova":      "SUPERNOVA",
        "swarm":     "ESSAIM DU VIDE",
        "blink":     "LE TRAIT DU NÉANT",
        "implosion": "L'IMPLOSION DU NÉANT",
        "lasers":    "LES AIGUILLES DU JUGEMENT",
        "summon":    "LES LÉGIONS DU VIDE",
        "spiral":    "SPIRALE BRISÉE",
        "dspiral":   "HÉLICE MAUDITE",
        "corrupt":   "LA CORRUPTION DU MONDE",
        "corrosion": "LA CORROSION DU VIDE",
        "combo":     "L'ENCHAÎNEMENT DIVIN",
    }
    _HEAVY = {"lasers", "summon", "implosion", "blink", "corrupt",
              "corrosion", "combo", "nova"}
    # Les composites « maison » pointent vers le nom canonique d'enchaînement ;
    # rings/sweep restent des attaques de base (sans bandeau).
    _ALIAS = {"combo_ws": "combo", "combo_rs": "combo", "combo_full": "combo",
              "collapse": "combo", "sweep2": "sweep"}
    # Réplique du dieu lancée AVEC l'attaque : on « entend » chaque spéciale.
    _SPEC_LINES = {
        "shotgun":   ["Reçois ma lumière.", "Aucun abri ne te protège."],
        "starfall":  ["Le ciel te juge.", "Cours — le ciel s'effondre."],
        "wall":      ["Trouve la faille. Vite.", "Une seule porte dans le Néant."],
        "nova":      ["RECULE.", "Tout s'embrase d'un souffle."],
        "swarm":     ["Mes yeux te traquent.", "Ils ne lâcheront pas ta trace."],
        "blink":     ["Trop lent pour me suivre.", "Je suis déjà sur toi."],
        "implosion": ["Le piège se referme.", "Une issue. Trouve-la, insecte."],
        "lasers":    ["Ma puissance n'a pas de limite.", "Que le jugement tourne."],
        "summon":    ["Mes légions ont faim.", "Tu n'es jamais seul devant moi."],
        "spiral":    ["Danse dans ma spirale.", "Tourne, petite chose."],
        "dspiral":   ["Deux hélices, aucune fuite.", "Le vertige du Néant."],
        "corrupt":   ["Ce monde m'appartient.", "Je reprends ce qui est mien.",
                      "Plus aucun sol pour les insectes."],
        "corrosion": ["Le sol te dévore.", "Ta chair fond comme le reste.",
                      "Rien ne demeure pur sous moi."],
        "combo":     ["Assez joué. MEURS.", "Voilà ce qu'est un dieu.",
                      "Encaisse. TOUT."],
    }

    def _announce(self, tok):
        tok = self._ALIAS.get(tok, tok)
        # On N'AFFICHE PLUS le nom des attaques à l'écran (demande joueur) :
        # seuls les titres de cinématique (COURROUX, NÉMÉSIS) restent. On garde
        # par contre les répliques/taunts du dieu ci-dessous.
        lines = self._SPEC_LINES.get(tok)
        if lines and hasattr(self.game, "set_subtitle"):
            self.game.set_subtitle(random.choice(lines), 80)
        if tok in self._HEAVY:
            self._cast_flourish(self._form_color(), 26)

    def _cast_flourish(self, color, frames=22):
        self._cast_anim = max(self._cast_anim, frames)
        self._cast_col = color

    # ── Interface combat ───────────────────────────────────────────────────
    def display_bar_fraction(self):
        if self.state == "intro":
            return 1.0
        if self.state == "transition":
            t = self.transition_t
            if t < 35:
                return max(0.0, 1.0 - t / 35)
            if t < 60:
                return 0.0
            return min(1.0, ((t - 60) / 35) ** 0.5)
        low, high = AEGIS_PHASE_HP_RANGES.get(self.phase, (0, 1))
        span = max(1, high - low)
        return max(0.0, min(1.0, (self.hp - low) / span))

    def take_dmg(self, dmg, current_dim, particles):
        if self.state in ("intro", "transition"): return 0
        if self.finale_active: return 0          # FINALE : on ne le tue pas en tapant
        if self.invuln_t > 0: return 0
        if self.final_blow_active: return 0
        self.hp -= dmg
        if self.hp < 0: self.hp = 0
        if self.hp == 0 and self.phase == 7:
            self.dead = True
            self.lasers = []; self.minions = []
            self.game.add_shake(22, 40)
            burst(particles, self.x, self.y, 90, _AEGIS_COL_DARK, 10.0, 70, 0.0, 6)
        self.hit_flash = 8
        if self._snd_hit: self._snd_hit.play()
        return dmg

    def hit_targets(self, current_dim):
        if self.state in ("intro", "transition"):
            return []
        class _T:
            def __init__(s, r): s.rect = r
        return [_T(self.rect)]

    def get_pull(self):
        # Phase 6 : aspiration ; phase 7 : aspiration renforcée (Le Néant)
        if self.state == "fighting":
            if self.phase == 7:
                return (self.x, self.y, 0.16)
            if self.phase == 6:
                return (self.x, self.y, 0.11)
        return (None, None, 0.0)

    def parry_hit(self, particles):
        # Aegis ne tire pas de projectiles parables pour l'instant ; no-op défensif
        # pour rester compatible avec _check_parry sans planter.
        self.hit_flash = 6
        burst(particles, self.x, self.y, 18, self._form_color(), 6.0, 40, 0.0, 4)

    # ── Rendu ──────────────────────────────────────────────────────────────
    def _draw_spiky_halo(self, surf, cx, cy, col, scale=1.0):
        """Couronne d'épines (le « soleil » du splat art) derrière Aegis."""
        n = 16
        base = self.vis * 0.95 * scale
        for i in range(n):
            a = self.bob_t * 0.25 + i * math.tau / n
            spk = base * (1.25 + 0.18 * math.sin(self.bob_t * 2 + i))
            x2 = cx + math.cos(a) * spk
            y2 = cy + math.sin(a) * spk
            w = max(2, int(7 * scale))
            pygame.draw.line(surf, col, (cx, cy), (int(x2), int(y2)), w)

    def draw(self, surf, cam, current_dim):
        if self.dead and self.death_t > 90:
            return
        cx = int(self.x - cam[0])
        cy = int(self.y + self.float_offset - cam[1])
        form = self._form()
        glow_col = self._form_color()
        vis = self.vis
        pulse = 0.75 + 0.25 * math.sin(self.bob_t * 1.5)

        # ── Mares de corrosion : nappes au sol, derrière tout le reste ───────
        for pool in self.pools:
            pool.draw(surf, cam)

        # ── Lasers Horloge : dessinés derrière Aegis (ils émanent de lui) ────
        for L in self.lasers:
            L.draw(surf, cam)
        # Aura de puissance pulsante tant que les aiguilles balaient l'arène
        if self.lasers:
            chg = 0.5 + 0.5 * math.sin(self._anim_t * 0.4)
            for k in range(3):
                rr = int(self.vis * (1.3 + k * 0.32))
                rs = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(rs, (*_AEGIS_COL_DARK2, int(38 + 52 * chg)),
                                   (rr + 2, rr + 2), rr, 3)
                surf.blit(rs, (cx - rr - 2, cy - rr - 2),
                          special_flags=pygame.BLEND_RGBA_ADD)

        # ── Aura de montée en puissance pendant la transition de phase ───────
        if self.state == "transition":
            big = self.next_phase in self._TRANS_MILESTONE
            ct = self.transition_t / (140.0 if big else 100.0)
            charge = min(1.0, ct * 1.6)
            # anneaux d'énergie convergents
            for k in range(4):
                rr = int(vis * (2.4 - k * 0.45) * (1.0 - charge * 0.55))
                if rr <= 2: continue
                aa = int((70 + 90 * charge) * (0.5 + 0.5 * math.sin(self._anim_t * 0.5 + k)))
                ring_s = pygame.Surface((rr * 2 + 6, rr * 2 + 6), pygame.SRCALPHA)
                col = _AEGIS_COL_DARK2 if (big and self.next_phase >= 4) else glow_col
                pygame.draw.circle(ring_s, (*col, min(255, aa)), (rr + 3, rr + 3), rr, 3)
                surf.blit(ring_s, (cx - rr - 3, cy - rr - 3),
                          special_flags=pygame.BLEND_RGBA_ADD)
            vis = int(self.vis * (1.0 + 0.12 * charge))   # le sprite « gonfle »

        # ── Couronne d'épines (formes mixed/dark : le masque tombe) ──────────
        if form != 'light':
            halo_surf = pygame.Surface((vis * 4, vis * 4), pygame.SRCALPHA)
            spike_col = (*_AEGIS_COL_DARK2, int(60 * pulse))
            self._draw_spiky_halo(halo_surf, vis * 2, vis * 2, spike_col,
                                  scale=1.0 if form == 'dark' else 0.7)
            surf.blit(halo_surf, (cx - vis * 2, cy - vis * 2),
                      special_flags=pygame.BLEND_RGBA_ADD)

        # ── Halo radial doux (dégradé additif → vraie lueur, pas de disque) ──
        gs = pygame.Surface((vis * 2, vis * 2), pygame.SRCALPHA)
        steps = 9
        for k in range(steps):
            rr = int(vis * (1 - k / steps))
            if rr <= 0: continue
            aa = int((10 + 7 * k) * pulse)
            pygame.draw.circle(gs, (*glow_col, aa), (vis, vis), rr)
        surf.blit(gs, (cx - vis, cy - vis), special_flags=pygame.BLEND_RGBA_ADD)

        # ── Flourish de canalisation : Aegis « charge » une attaque lourde ───
        # Halo qui se contracte + éclats qui convergent : un tell clair de dieu.
        if self._cast_anim > 0:
            # fr borné à 1.0 : un flourish long (combo) tient à pleine intensité
            # puis s'estompe sur les 24 dernières frames — sinon l'alpha déborde
            # de [0,255] et pygame plante (ValueError couleur).
            fr = min(1.0, self._cast_anim / 24.0)
            col = self._cast_col
            for k in range(3):
                rr = int(vis * (1.7 - k * 0.3) * (0.55 + 0.7 * fr))
                if rr <= 2: continue
                cs = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(cs, (*col, int(120 * fr)), (rr + 2, rr + 2), rr, 3)
                surf.blit(cs, (cx - rr - 2, cy - rr - 2),
                          special_flags=pygame.BLEND_RGBA_ADD)
            nseg = 8
            base = self._anim_t * 0.25
            rad = int(vis * (1.5 - 0.7 * fr))
            for i in range(nseg):
                a = base + i * math.tau / nseg
                ex = int(cx + math.cos(a) * rad); ey = int(cy + math.sin(a) * rad)
                seg = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(seg, (*col, int(200 * fr)), (5, 5), 4)
                surf.blit(seg, (ex - 5, ey - 5), special_flags=pygame.BLEND_RGBA_ADD)

        # Choix de la planche recolorisée selon la forme
        if form == 'dark':
            sheet = getattr(self.game, '_aegis_sheet_dark', None) \
                    or getattr(self.game, '_aegis_sheet', None)
        elif form == 'mixed':
            sheet = getattr(self.game, '_aegis_sheet_mixed', None) \
                    or getattr(self.game, '_aegis_sheet', None)
        else:
            sheet = getattr(self.game, '_aegis_sheet', None)

        if sheet:
            fw = getattr(self.game, '_aegis_frame_w', sheet.get_height())
            nframes = max(1, sheet.get_width() // fw)
            fi = (self._anim_t // 4) % nframes
            try:
                frame = sheet.subsurface((fi * fw, 0, fw, sheet.get_height()))
            except Exception:
                frame = sheet.subsurface((0, 0, fw, sheet.get_height()))
            # Léger tremblement quand le vrai visage est révélé
            jit = int(math.sin(self._anim_t * 1.7) * 2) if form == 'dark' else 0
            scaled = pygame.transform.scale(frame, (vis * 2, vis * 2)).copy()

            # Flash blanc quand touché — BLEND_RGB_ADD éclaircit uniquement les
            # pixels du sprite (alpha préservé) : plus de carré blanc autour.
            if self.hit_flash > 0:
                add = min(210, self.hit_flash * 26)
                scaled.fill((add, add, add, 0), special_flags=pygame.BLEND_RGB_ADD)
            # Dissolution en mourant
            if self.dead:
                scaled.set_alpha(max(0, 255 - int(self.death_t * 3)))
            surf.blit(scaled, (cx - vis + jit, cy - vis))
        else:
            pygame.draw.circle(surf, glow_col, (cx, cy), self.radius)
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), self.radius, 3)

        # ── Invocations du Vide (yeux flottants, devant Aegis) ───────────────
        for m in self.minions:
            m.draw(surf, cam)


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

STATE_TITLE      = "title"
STATE_CINEMATIC  = "cinematic"
STATE_OVERWORLD  = "overworld"
STATE_HUB        = "hub"
STATE_MOON       = "moon"
STATE_VICTORY    = "victory"
STATE_GAMEOVER   = "gameover"

# ── Overworld — carte de départ (32×20 tuiles, OW_TILE px chacune) ──────────
OW_TILE     = 40
OW_FLOOR    = 0
OW_WALL     = 1
OW_PORTAL_M = 2      # portail vers Boss Lune

_OW_TILES = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,1],
    [1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,2,0,0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,2,0,0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,1],
    [1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]
_OW_SPAWN_COL, _OW_SPAWN_ROW = 15, 13

# ── Dialogues cinématique d'ouverture (Aegis angélique réveille le héros) ───
_CIN_LINES = [
    "...",
    "Réveille-toi, enfant.",
    "Je suis Aegis, gardien de la Terre.\nTu as été choisi pour libérer ce monde.",
    "Des faux dieux corrompent les âmes\ndepuis des millénaires. Le peuple souffre.",
    "Commence par la Lune. Son temple est\nau nord de ce sanctuaire.",
    "Va, Enfant Élu.\nJe serai toujours là pour te guider.",
]

# Dialogue Aegis après chaque boss (fin de combat)
_AEGIS_BOSS_LINES = [
    "Bien joué, Enfant Élu.",
    "Cette créature était puissante...\nmais tu l'as affaiblie pour moi.",
    "Je suis là pour veiller sur toi.\nNe t'inquiète pas.",
    "D'autres faux dieux vous attendent encore.\nTon chemin ne fait que commencer...",
]

# Lignes de fin — mort d'Aegis (boss final)
_AEGIS_DEATH_LINES = [
    "...Incroyable.",
    "Un mortel... m'a vaincu.",
    "L'univers respire de nouveau.",
    "Mais quelque part... un héros se demande",
    "si c'était vraiment une victoire.",
]

# Tonalité des « voix » d'écriture (Hz) : chaque perso a son bip, + ou - grave.
_VOICE_AEGIS      = 330.0   # Aegis angélique (intro tuto, fin de combat) — grave
_VOICE_AEGIS_VOID = 200.0   # Aegis combat / cinématiques / Vide — TRÈS grave
_VOICE_MOON       = 680.0   # la Lune (Derniers Recours) — plus aigu
_VOICE_HERO       = 150.0   # le héros (« Je suis la fin. ») — abyssal, glaçant

# ── FINALE — timelines (frames @ ~60 fps) ───────────────────────────────────
# Prélude : la fissure se forme TRÈS lentement, puis les mains l'arrachent.
_FIN_HANDS = 660    # surgissement des mains (animation de spawn + secousse d'écran)
_FIN_TEAR  = 760    # début de l'arrachage (les mains tirent le néant)
_FIN_OPEN  = 1080   # écart complet sur le néant
_FIN_PRELUDE_END = 1280
# Exécution (time-stop) : gel → Aegis surpris → le héros révèle sa VRAIE FORME
# → « Qui es-tu ? / Je suis la fin. » → déluge façon Susano'o (~16 s, très agressif,
# Aegis implore/s'énerve/sombre) → Aegis réduit en CENDRES → fin.
_FIN_SURPRISE = 80
_FIN_REVEAL   = 280
_FIN_QUESTION = 560
_FIN_ANSWER   = 760
_FIN_BARRAGE  = 940
_FIN_ASH      = 1920    # déluge ≈ 980 frames ≈ 16,3 s
_FIN_ASH_END  = 2150    # → acte « ending »


class OverworldPlayer:
    """Personnage vue de dessus pour l'exploration (style Pokémon)."""
    SPD  = 4
    HALF = 14   # demi-taille hitbox px

    def __init__(self, x, y):
        self.x       = float(x)
        self.y       = float(y)
        self.facing  = "down"
        self.walk_t  = 0

    def _rect(self):
        h = self.HALF
        return pygame.Rect(int(self.x) - h, int(self.y) - h, h * 2, h * 2)

    def update(self, keys, walls):
        dx = dy = 0.0
        if keys[pygame.K_UP]    or keys[pygame.K_z]: dy -= self.SPD; self.facing = "up"
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += self.SPD; self.facing = "down"
        if keys[pygame.K_LEFT]  or keys[pygame.K_q]: dx -= self.SPD; self.facing = "left"
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += self.SPD; self.facing = "right"
        if dx and dy:
            dx *= 0.707; dy *= 0.707
        if dx or dy:
            self.walk_t += 1
        h = self.HALF
        # X
        self.x += dx
        r = self._rect()
        for w in walls:
            if r.colliderect(w):
                if dx > 0: self.x = w.left  - h
                else:      self.x = w.right + h
        # Y
        self.y += dy
        r = self._rect()
        for w in walls:
            if r.colliderect(w):
                if dy > 0: self.y = w.top    - h
                else:      self.y = w.bottom + h

    def draw(self, surf, cam, frame):
        sx = int(self.x) - cam[0]
        sy = int(self.y) - cam[1]
        # Ombre portée
        shad = pygame.Surface((28, 10), pygame.SRCALPHA)
        shad.fill((0, 0, 0, 55))
        surf.blit(shad, (sx - 14, sy + 10))
        # Corps
        pygame.draw.circle(surf, (170, 120, 80), (sx, sy), 13)
        pygame.draw.circle(surf, (230, 185, 130), (sx, sy), 9)
        # Indicateur direction
        d = {"up": (0,-1), "down": (0,1), "left": (-1,0), "right": (1,0)}[self.facing]
        pygame.draw.circle(surf, (255, 230, 170), (sx + d[0]*12, sy + d[1]*12), 4)


class Game:
    def __init__(self):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        self.fullscreen = False
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
        self.heal_orbs = []
        self.starfield = StarField()
        self.dust = DustField(60, bounds=(-200, 0, 1500, 720))

        # ── Assets UI barre HP ────────────────────────────────────────────────
        _base_dir_ui = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        def _load_ui(name, scale):
            try:
                raw = pygame.image.load(
                    os.path.join(_base_dir_ui, "assets", "images", name)
                ).convert_alpha()
                sw, sh = raw.get_width() * scale, raw.get_height() * scale
                return pygame.transform.scale(raw, (sw, sh))
            except Exception:
                return None

        # Boss HP bar  (Health_03 — 128×32 src, fill x=24..107 y=14..17)
        # Scale uniforme ×3 → 384×96 — proportions respectées, pas d'étirement
        _BS = 3
        self._hp_frame    = _load_ui("hp_bar_frame.png", _BS)
        self._hp_fill     = _load_ui("hp_bar_fill.png",  _BS)
        self._hp_fw       = 128 * _BS               # 384
        self._hp_fh       = 32  * _BS               # 96
        self._hp_fill_x0  = 24  * _BS               # 72
        self._hp_fill_w   = 84  * _BS               # 252
        self._hp_fill_y0  = 14  * _BS               # 42  (y dans surf scalée)

        # Hero HP bar — assets plus utilisés (barre procédurale avec cadran doré)
        self._hero_frame = None
        self._hero_fill  = None

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
        # Flash plein écran (impacts, transitions de phase)
        self.flash_t = 0
        self.flash_max = 1
        self.flash_col = (255, 255, 255)
        # Titre de forme affiché pendant les transitions Aegis
        self.subtitle_text = ""
        self.subtitle_t = 0
        self.subtitle_max = 1

        self.player = None
        self.platforms = []
        self.portals = []
        self.boss = None
        self.frame = 0

        self.announce_text = ""
        self.announce_t = 0
        self.announce_max = 110

        # Bandeau « nom d'attaque » : on VOIT les attaques spéciales d'Aegis
        self.callout_text = ""
        self.callout_t = 0
        self.callout_max = 1

        self.show_controls_popup = False
        self.title_pulse_t = 0
        self.start_btn_rect = pygame.Rect(0, 0, 0, 0)  # mis à jour dans draw_title
        self.start_phase5_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.start_aegis_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.p_press_times = []
        self.phase5_unlocked = False
        self.phase5_mode = False
        # Boss final Aegis (accès debug : P×20 en <5s)
        self.aegis_unlocked = False
        self.fighting_aegis = False
        self.aegis_ending_t = 0
        self.finale_gauge = 0.0   # jauge « ?! » de la VRAIE fin (se remplit en survivant)
        self.finale_done = False  # vrai une fois le texte final affiché (débloque [R])
        self._skip_charge = 0.0   # spam Espace/Entrée pour passer une cinématique
        self.p5_cinematic_t = 0   # >0 while phase-5 intro plays (180 frames total)

        self.god_mode = False
        self.show_god_dialog = False
        self.god_input = ""
        self.pre_dr_zoom_t = 0
        self.post_dr_dialog_t = 0
        self.final_blow_dialog_t = 0
        self.victory_timer = 0        # compte à rebours après mort boss → hub
        self.final_blow_hub_t = 0     # idem, piloté par update_moon sans STATE_VICTORY
        # Épée divine
        self.sword_y = -200
        self.sword_x = WIDTH // 2
        self.sword_visible = False
        self.boss_crack_active = False
        self.boss_split_t = 0
        self.boss_split_cx = 0
        self.boss_split_cy = 0
        self.boss_qmark_t = 0       # >0 pendant la pause épée (phase WAIT)
        self.dream_exit_flash = 0
        self.settings_open = False
        self._settings_path = os.path.join(os.path.expanduser("~"), ".dreamspawn_settings.json")
        self.music_vol = 0.03
        self.sfx_vol   = 0.15
        self.controls_scroll = 0
        self._load_settings()

        # ── Voix d'écriture : un blip par personnage (style Undertale) ────────
        self._blips = {}           # cache  freq(Hz) -> pygame.Sound (None si pas d'audio)
        self._sfx_bank = {}        # cache  nom -> pygame.Sound (effets jouables partout)
        self._voice_queue = []     # rafales de blips programmées : [frames_restantes, freq]
        self._cine_spoken = set()  # répliques de cinématique déjà « parlées » (1× / combat)

        # ── Overworld ─────────────────────────────────────────────────────────
        self.ow_player  = None
        self.ow_walls   = []
        self.ow_portals = []
        self.ow_cam     = [0, 0]

        # ── Cinématique d'ouverture ───────────────────────────────────────────
        self.cin_line   = 0
        self.cin_char_t = 0
        self.cin_hold_t = 0
        self.cin_fade   = 0   # 0→60 = fade-in, reste à 60 ensuite

        # ── Pause (overworld, combat Lune/Aegis, hub) ─────────────────────────
        self.paused     = False
        self.pause_sel  = 0

        # ── Animation sauvegarde (style DS) ───────────────────────────────────
        self.save_anim_t   = 0     # 0=inactif, 1→150=animation
        self.SAVE_ANIM_DUR = 150

        # ── Compétence Bouclier (débloquée par Aegis après Boss Lune) ─────────
        self.shield_unlocked    = False
        self.ability_shield_t   = 0    # frames actif restantes (120 = 2s)
        self.ability_shield_cd  = 0    # cooldown restant (300 = 5s)
        self.SHIELD_DUR         = 120
        self.SHIELD_CD          = 300

        # ── Dialogue Aegis post-boss ───────────────────────────────────────────
        self.aegis_dialog_active  = False
        self.aegis_dialog_line    = 0
        self.aegis_dialog_char_t  = 0
        self.aegis_dialog_fade    = 0
        # Sprite Aegis angélique (14 frames 240×240, animé)
        self._aegis_sheet   = None
        self._aegis_frame_w = 240
        self._aegis_anim_t  = 0
        try:
            # Les assets sont dans dreamspawn/assets/, un niveau au-dessus de src/
            _src_dir  = os.path.dirname(os.path.abspath(__file__))
            _root_dir = getattr(sys, '_MEIPASS', os.path.dirname(_src_dir))
            _aegis_path = os.path.join(_root_dir, "assets", "images", "aegis_final.png")
            _raw  = pygame.image.load(_aegis_path).convert_alpha()
            _raw  = _strip_black_bg(_raw)   # supprime le fond noir (carré moche)
            self._aegis_sheet   = _raw
            self._aegis_frame_w = _raw.get_height()   # frames carrés (240px)
            # Variantes recolorisées (préservent le détail du sprite) :
            #  - mixed : le masque doré se fissure de magenta
            #  - dark  : vrai visage « splat art » violet→rose vif
            self._aegis_sheet_mixed = _recolor_gradient(_raw, (70, 25, 70), (255, 150, 90))
            self._aegis_sheet_dark  = _recolor_gradient(_raw, (35, 4, 55), (255, 95, 215))
        except Exception as e:
            print(f"[AEGIS] ERREUR chargement: {e}")
            self._aegis_sheet = None
            self._aegis_sheet_mixed = None
            self._aegis_sheet_dark = None

        # Slot UI Soulslike (Abyss theme — extrait depuis ui_slot.png)
        self._ui_slot = None
        try:
            _slot_path = os.path.join(_root_dir, "assets", "images", "ui_slot.png")
            _slot_sheet = pygame.image.load(_slot_path).convert_alpha()
            # La grille INVENTORY-Abyss est 4×3 ; premier slot à (~6, 28), taille ~28×28
            _cell = _slot_sheet.subsurface((6, 28, 28, 28))
            self._ui_slot = pygame.transform.scale(_cell, (64, 64))
        except Exception as e:
            print(f"[UI] Erreur slot: {e}")
            self._ui_slot = None

    def _load_settings(self):
        try:
            with open(self._settings_path, 'r') as f:
                data = json.load(f)
            # music_vol ignoré volontairement : volume forcé à 5% depuis le code
            self.sfx_vol = float(data.get("sfx_vol", 0.15))
        except Exception:
            pass
        # Volume musique toujours forcé à 5% indépendamment des sauvegardes
        self.music_vol = 0.03
        try:
            pygame.mixer.music.set_volume(0.03)
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(self._settings_path, 'w') as f:
                json.dump({"music_vol": self.music_vol, "sfx_vol": self.sfx_vol}, f)
        except Exception:
            pass

    def _apply_sfx_vol(self):
        snds = []
        if self.player:
            if getattr(self.player, '_snd_jump', None): snds.append(self.player._snd_jump)
            if getattr(self.player, '_snd_swap', None): snds.append(self.player._snd_swap)
        if self.boss and getattr(self.boss, '_snd_laser', None):
            snds.append(self.boss._snd_laser)
        for s in snds:
            if s: s.set_volume(self.sfx_vol)

    def draw_settings_overlay(self):
        W, H = 420, 180
        ox = (WIDTH - W) // 2
        oy = (HEIGHT - H) // 2
        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        panel.fill((10, 0, 25, 210))
        pygame.draw.rect(panel, (120, 80, 200), (0, 0, W, H), 2)
        self.screen.blit(panel, (ox, oy))
        title = self.font_med.render("PARAMETRES AUDIO", True, (200, 160, 255))
        self.screen.blit(title, (ox + W // 2 - title.get_width() // 2, oy + 14))
        self._draw_slider(ox + 30, oy + 65,  W - 60, "MUSIQUE", self.music_vol)
        self._draw_slider(ox + 30, oy + 120, W - 60, "EFFETS",  self.sfx_vol)
        hint = self.font_sm.render("TAB pour fermer", True, (120, 100, 160))
        self.screen.blit(hint, (ox + W // 2 - hint.get_width() // 2, oy + H - 22))

    def _draw_slider(self, x, y, w, label, value):
        lbl = self.font_sm.render(label, True, (180, 140, 240))
        self.screen.blit(lbl, (x, y - 18))
        pygame.draw.rect(self.screen, (50, 30, 80),  (x, y, w, 12), border_radius=6)
        fill_w = int(w * value)
        if fill_w > 0:
            pygame.draw.rect(self.screen, (140, 80, 220), (x, y, fill_w, 12), border_radius=6)
        cx = x + fill_w
        pygame.draw.circle(self.screen, (220, 180, 255), (cx, y + 6), 9)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, y + 6), 5)
        pct = self.font_sm.render(f"{int(value*100)}%", True, (200, 180, 230))
        self.screen.blit(pct, (x + w + 8, y - 2))

    def handle_settings_mouse(self, mx, my):
        W, H = 420, 180
        ox = (WIDTH - W) // 2
        oy = (HEIGHT - H) // 2
        sw = W - 60
        sx = ox + 30
        if oy + 56 <= my <= oy + 80:
            self.music_vol = max(0.0, min(1.0, (mx - sx) / sw))
            try: pygame.mixer.music.set_volume(self.music_vol)
            except: pass
            self._save_settings()
        if oy + 111 <= my <= oy + 135:
            self.sfx_vol = max(0.0, min(1.0, (mx - sx) / sw))
            self._apply_sfx_vol()
            self._save_settings()

    def play_sfx(self, name, vol=1.0):
        """Joue un effet sonore par NOM (assets/sounds/<name>.mp3), caché au 1er usage.
        Respecte le volume SFX des réglages. Sans danger si l'audio est absent."""
        if name not in self._sfx_bank:
            try:
                self._sfx_bank[name] = pygame.mixer.Sound(_asset_path("assets", "sounds", name + ".mp3"))
            except Exception:
                self._sfx_bank[name] = None
        s = self._sfx_bank[name]
        if s:
            try:
                s.set_volume(max(0.0, min(1.0, self.sfx_vol * vol))); s.play()
            except Exception:
                pass

    def _play_music(self, filename, volume=None, loops=-1, fadein_ms=1500):
        path = _asset_path("assets", "music", filename)
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume if volume is not None else self.music_vol)
            pygame.mixer.music.play(loops, fade_ms=fadein_ms)
        except Exception:
            pass

    # ── Son d'écriture (« blip » généré à la volée, sans fichier) ─────────────
    def _make_blip(self, freq=_VOICE_AEGIS, ms=40, amp=0.5):
        """Petit blip d'écriture (onde carrée + extinction rapide), généré en
        numpy pour coller au format du mixer. Renvoie None si indisponible."""
        try:
            import numpy as _np
            init = pygame.mixer.get_init()
            if not init:
                return None
            rate, _size, chans = init
            n  = max(1, int(rate * ms / 1000.0))
            tt = _np.arange(n, dtype=_np.float32) / float(rate)
            wave = _np.sign(_np.sin(2.0 * _np.pi * freq * tt))   # carré (8-bit)
            env  = _np.exp(-tt * 42.0)                           # decay rapide
            sig  = (wave * env * amp * 32767.0).astype(_np.int16)
            if chans and chans >= 2:
                sig = _np.repeat(sig.reshape(n, 1), chans, axis=1)
            return pygame.sndarray.make_sound(_np.ascontiguousarray(sig))
        except Exception:
            return None

    def _play_text_blip(self, freq=_VOICE_AEGIS):
        """Joue le blip de la voix `freq` (construit/caché paresseusement)."""
        key = int(freq)
        if key not in self._blips:
            self._blips[key] = self._make_blip(freq)   # peut être None (sans audio)
        snd = self._blips[key]
        if snd:
            try:
                snd.set_volume(max(0.0, min(1.0, self.sfx_vol)))
                snd.play()
            except Exception:
                pass

    def _typewriter_blip(self, line, t_before, t_after, freq=_VOICE_AEGIS):
        """Blip quand une nouvelle lettre apparaît (throttle ~1/2, hors espaces)."""
        txt = line.replace('\n', '')
        a = min(len(txt), t_before // 2)
        b = min(len(txt), t_after  // 2)
        if b <= a:
            return
        idx = b - 1
        if 0 <= idx < len(txt) and not txt[idx].isspace() and (b % 2 == 0):
            self._play_text_blip(freq)

    def _play_voice_line(self, freq=_VOICE_AEGIS_VOID, n=4, gap=3):
        """Programme une courte RAFALE de blips = « le perso prononce une ligne »."""
        for i in range(n):
            self._voice_queue.append([i * gap, freq])

    def _tick_voice_queue(self):
        """Joue les blips de voix arrivés à échéance (appelé chaque frame de jeu)."""
        if not self._voice_queue:
            return
        keep = []
        for e in self._voice_queue:
            e[0] -= 1
            if e[0] <= 0:
                self._play_text_blip(e[1])
            else:
                keep.append(e)
        self._voice_queue = keep

    def _cine_voice_once(self, key, freq=_VOICE_AEGIS_VOID):
        """Déclenche la voix d'une réplique de cinématique UNE seule fois (anti-spam)."""
        if key in self._cine_spoken:
            return
        self._cine_spoken.add(key)
        self._play_voice_line(freq)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            # SCALED maintient la résolution interne 1280×720 et scale à l'écran
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT),
                                                   pygame.FULLSCREEN | pygame.SCALED)
        else:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

    def reset_to_title(self):
        self.state = STATE_TITLE
        try:
            pygame.mixer.music.stop(); pygame.mixer.stop()   # coupe musique + SFX
        except Exception:
            pass
        self.phase5_mode = False
        self.fighting_aegis = False
        self.aegis_dialog_active = False
        self.paused = False
        self.particles = []
        self.projectiles_boss = []
        self.beams = []
        self.rings = []
        self.telegraphs = []
        self.arrows = []
        self.damage_numbers = []
        self.heal_orbs = []

    def start_hub(self):
        self.fighting_aegis = False
        self.particles.clear()
        self.projectiles_boss.clear()
        self.beams.clear()
        self.rings.clear()
        self.telegraphs.clear()
        self.arrows.clear()
        self.damage_numbers.clear()
        self.heal_orbs.clear()
        self.victory_timer = 0
        self.final_blow_hub_t = 0
        self.sword_visible = False
        self.boss_crack_active = False
        self.boss_split_t = 0
        self.boss_qmark_t = 0
        try:
            pygame.mixer.music.fadeout(1500)
        except Exception:
            pass
        self.platforms, self.portals, spawn = make_hub()
        self.player = Player(*spawn)
        self.cam = [0, 0]
        self.state = STATE_HUB

    def start_moon(self):
        self.aegis_dialog_active = False
        self.fighting_aegis = False
        self.particles.clear()
        self.projectiles_boss.clear()
        self.beams.clear()
        self.rings.clear()
        self.telegraphs.clear()
        self.arrows.clear()
        self.damage_numbers.clear()
        self.heal_orbs.clear()
        self.pre_dr_zoom_t = 0
        self.post_dr_dialog_t = 0
        self.final_blow_dialog_t = 0
        self.platforms, spawn = make_moon_arena()
        self.player = Player(*spawn)
        self.boss = MoonBoss(640, 360, self)
        if self.phase5_mode:
            # Sauter directement à la phase 5 (HP dans la plage 0-200)
            self.boss.phase = 5
            self.boss.hp = 200
            self.boss.state = "fighting"
            self.boss.intro_t = 0
            # Positionner le boss directement à sa position de combat
            self.boss.x = self.boss.cx
            self.boss.y = self.boss.cy - 140
        self.cam = [0, 0]
        self.state = STATE_MOON
        self.victory_timer = 0
        self.final_blow_hub_t = 0
        self.sword_visible = False
        self.boss_crack_active = False
        self.boss_split_t = 0
        self.boss_qmark_t = 0
        self.dream_exit_flash = 0
        self._play_music("boss_moon.mp3", fadein_ms=2000)

    def start_aegis_fight(self):
        """Lance directement le combat final Aegis (7 phases)."""
        self.aegis_dialog_active = False
        self._cine_spoken = set()   # ré-autorise les répliques de cinématique
        self._voice_queue = []
        self.finale_gauge = 0.0
        self.finale_done = False
        self.fighting_aegis = True
        self.aegis_ending_t = 0
        self.shield_unlocked = True   # toutes les compétences dispo pour ce combat
        self.particles.clear()
        self.projectiles_boss.clear()
        self.beams.clear()
        self.rings.clear()
        self.telegraphs.clear()
        self.arrows.clear()
        self.damage_numbers.clear()
        self.heal_orbs.clear()
        self.pre_dr_zoom_t = 0
        self.post_dr_dialog_t = 0
        self.final_blow_dialog_t = 0
        self.platforms, spawn = make_moon_arena()
        # Contre AEGIS, la « Fissure » (switch de dimension) n'existe pas : c'est la
        # mécanique signature de la LUNE. On fige le héros en RÉALITÉ et on rend
        # toutes les plateformes visibles (sinon les plateformes-rêve seraient mortes).
        for _p in self.platforms:
            _p.dim_only = None
        self.player = Player(*spawn)
        self.player.can_swap = False
        self.player.dimension = DIM_REAL
        self.boss = AegisBoss(640, 360, self)
        self.cam = [0, 0]
        self.state = STATE_MOON
        self.victory_timer = 0
        self.final_blow_hub_t = 0
        self.sword_visible = False
        self.boss_crack_active = False
        self.boss_split_t = 0
        self.boss_qmark_t = 0
        self.dream_exit_flash = 0
        self.ability_shield_t = 0
        self.ability_shield_cd = 0
        self._play_music("boss_moon.mp3", fadein_ms=2000)

    def _boss_cine_kind(self):
        """Renvoie la cinématique-attaque scriptée active : 'nemesis', 'courroux' ou None."""
        b = self.boss
        if not isinstance(b, AegisBoss):
            return None
        if getattr(b, "nemesis_active", False):
            return "nemesis"
        if getattr(b, "courroux_active", False):
            return "courroux"
        return None

    def _finale_cine(self):
        """Vrai pendant un acte CINÉMATIQUE de la FINALE (gel de l'input).
        L'acte « survival » N'EST PAS gelé : le héros doit pouvoir esquiver."""
        b = self.boss
        return bool(isinstance(b, AegisBoss) and getattr(b, "finale_active", False)
                    and b.finale_act != "survival")

    def _finale_survival(self):
        """Vrai pendant la SURVIE de la finale (esquive jouable, pouvoirs coupés)."""
        b = self.boss
        return bool(isinstance(b, AegisBoss) and getattr(b, "finale_active", False)
                    and b.finale_act == "survival")

    def _input_locked(self):
        """Gameplay gelé pendant une cinématique non-interactive (NÉMÉSIS, COURROUX, ENTRÉE, FINALE)."""
        if self._boss_cine_kind() is not None:
            return True
        if self._finale_cine():
            return True
        if (self.boss and isinstance(self.boss, AegisBoss)
                and getattr(self.boss, "state", "") == "intro"):
            return True
        return False

    def _skippable(self):
        """Cinématique NON-jouable en cours, qu'on peut passer (spam Espace/Entrée).
        La survie de la finale (jouable) n'en fait PAS partie."""
        b = self.boss
        if not isinstance(b, AegisBoss):
            return None
        if getattr(b, "nemesis_active", False):  return "nemesis"
        if getattr(b, "courroux_active", False): return "courroux"
        if getattr(b, "finale_active", False) and b.finale_act != "survival": return "finale"
        if getattr(b, "state", "") == "intro":   return "intro"
        return None

    def _skip_cinematic(self):
        """Passe la cinématique en cours (saute à sa fin / à l'acte suivant)."""
        b = self.boss; kind = self._skippable()
        if kind == "intro":
            b.intro_t = 9999                          # prochain tick → "fighting"
        elif kind == "nemesis":
            b.nemesis_t = b.nemesis_dur - 1           # prochain tick → bloc de fin
        elif kind == "courroux":
            if not b._cx_hp_set:                      # applique la frappe si pas faite
                self.player.hp = max(1, self.player.hp - max(2, self.player.max_hp // 2))
                b._cx_hp_set = True
            b.courroux_t = b.courroux_dur - 1
        elif kind == "finale":
            act = b.finale_act
            if act == "prelude":
                b.finale_act = "dialogue"; b.finale_t = 0
            elif act == "dialogue":
                b.finale_act = "survival"; b.finale_t = 0
                b.finale_fire_t = 0; self.finale_gauge = 0.0
                self.player.invuln = max(self.player.invuln, 40)
            elif act == "timestop":
                if not b.dead:                        # réduit Aegis en cendres si pas fait
                    b.dead = True; b.death_t = 999
                    self.projectiles_boss[:] = []; self.beams[:] = []; self.rings[:] = []
                b.finale_t = _FIN_ASH_END             # prochain tick → "ending"
            elif act == "ending":
                b.finale_t = 902; self.finale_done = True

    def _skip_press(self):
        """Une pression Espace/Entrée pendant une cinématique → charge le skip."""
        if not self._skippable():
            return
        self._skip_charge += 38.0
        if self._skip_charge >= 100.0:
            self._skip_charge = 0.0
            self._skip_cinematic()

    def _draw_skip_hint(self):
        """Indice + jauge de spam pour passer la cinématique."""
        if not self._skippable():
            return
        W, H = WIDTH, HEIGHT
        s = self.font_sm.render("Espace / Entrée : passer  >>", True, (210, 210, 222))
        s.set_alpha(165)
        r = s.get_rect(bottomright=(W - 20, H - 16))
        self.screen.blit(s, r)
        pygame.draw.rect(self.screen, (50, 26, 44), (r.left, r.bottom + 3, 130, 4))
        if self._skip_charge > 0:
            bw = int(130 * min(1.0, self._skip_charge / 100.0))
            pygame.draw.rect(self.screen, (255, 120, 200), (r.left, r.bottom + 3, bw, 4))

    def _finale_activate_skill(self):
        """Le héros déclenche « ?! » : LE TEMPS S'ARRÊTE → exécution du dieu."""
        b = self.boss
        if not self._finale_survival() or self.finale_gauge < 1.0:
            return
        b._fin_hero0 = self.player.rect.center      # point de départ du saut fatal
        b.finale_act = "timestop"
        b.finale_t = 0
        b._fin_cut = False
        b._fin_revealed = False
        self._fin_trail = []                        # après-images du héros
        self._fin_fists = []; self._fin_impacts = []; self._fin_camshake = 0.0; self._fin_surge_T = 40
        self._fin_hitstop = 0
        self.player._void_form = False; self.player._void_u = 0.0
        self.flash((200, 220, 255), 16)             # onde de gel
        # Les projectiles restent SUSPENDUS (le temps gèle) : update_moon ne les
        # fait plus avancer pendant l'acte time-stop.

    def _update_finale_cine(self):
        """Pilote les actes CINÉMATIQUES de la finale : prélude → dialogue →
        time-stop (exécution) → fin. La SURVIE, elle, tourne en gameplay normal."""
        b = self.boss
        if getattr(self, "_fin_hitstop", 0) > 0:        # GEL D'IMPACT (hit-stop brutal)
            self._fin_hitstop -= 1
            for part in self.particles: part.update()
            self.particles[:] = [pp for pp in self.particles if pp.alive()]
            self._fin_camshake = getattr(self, "_fin_camshake", 0.0) * 0.9
            return
        b.finale_t += 1
        t = b.finale_t
        act = b.finale_act
        self.cam = [0, 0]
        b.bob_t += 0.04
        b._anim_t += 1                       # le sprite reste animé pendant les actes
        b.float_offset = math.sin(b.bob_t) * 10
        self.player.invuln = max(self.player.invuln, 8)
        # Braises ascendantes autour du dieu (ambiance), sauf après la coupe.
        if act in ("dialogue",) and t % 5 == 0 and not b._fin_cut:
            burst(self.particles, b.x + random.randint(-b.vis // 2, b.vis // 2),
                  b.y + random.randint(-20, b.vis // 2), 1, _AEGIS_COL_DARK2, 1.3, 60, -0.03, 3)
        for part in self.particles: part.update()
        self.particles[:] = [p for p in self.particles if p.alive()]
        if self.announce_t > 0: self.announce_t -= 1
        if self.flash_t > 0: self.flash_t -= 1
        if self.subtitle_t > 0: self.subtitle_t -= 1
        if self.callout_t > 0: self.callout_t -= 1
        self.starfield.update(); self.dust.update()

        if act == "prelude":
            # FISSURE TRÈS LENTE (0→_FIN_TEAR) : elle se forme petit à petit ; les
            # étincelles s'intensifient avec le temps. Puis les MAINS surgissent.
            if t == 1:
                self.flash((30, 4, 22), 10)         # léger assombrissement, pas de flash blanc
            if t > 120 and t % max(3, 12 - t // 110) == 0:   # crépitement croissant
                spread = int(50 + t * 0.45)
                burst(self.particles, WIDTH // 2 + random.randint(-26, 26),
                      HEIGHT // 2 + random.randint(-spread, spread),
                      2, _AEGIS_COL_DARK2, 2.2, 40, 0.0, 4)
            if t == _FIN_HANDS:                     # SPAWN des mains : grosse secousse
                self.add_shake(28, 90)
                self.play_sfx("boss_explosion", 0.7)
                burst(self.particles, WIDTH // 2, HEIGHT // 2, 90, _AEGIS_COL_DARK2, 7.5, 54, 0.0, 6)
                burst(self.particles, WIDTH // 2, HEIGHT // 2, 40, (255, 255, 255), 5.0, 36, 0.0, 5)
            if t == _FIN_TEAR:                      # début de l'arrachage : 2e secousse
                self.add_shake(18, 60)
            if t > _FIN_TEAR and t % 5 == 0:
                burst(self.particles, b.x + random.randint(-80, 80), b.y + random.randint(-60, 60),
                      3, _AEGIS_COL_DARK2, 3.2, 42, 0.0, 4)
            if self.shake > 0:                      # la secousse retombe seule
                self.shake -= 1
            if t >= _FIN_PRELUDE_END:
                b.finale_act = "dialogue"; b.finale_t = 0

        elif act == "dialogue":
            # Blip au début de chaque réplique d'AEGIS (les « ... » du héros = silence).
            if t in (1, 200, 610, 1000):
                self._play_text_blip(_VOICE_AEGIS_VOID)   # voix grave du Vide
            if t % 9 == 0:
                burst(self.particles, random.randint(0, WIDTH), random.randint(0, HEIGHT),
                      1, _AEGIS_COL_VOID, 0.8, 55, 0.0, 3)
            if t >= 1140:
                b.finale_act = "survival"; b.finale_t = 0
                b.finale_fire_t = 0
                self.finale_gauge = 0.0
                self.player.invuln = max(self.player.invuln, 40)

        elif act == "timestop":
            # EXÉCUTION : gel → Aegis surpris → le héros révèle sa VRAIE FORME →
            # « Qui es-tu ? / Je suis la fin. » → DÉLUGE (façon Susano'o, ~16 s,
            # Aegis implore/s'énerve/sombre) → Aegis réduit en CENDRES.
            stance = (640, 442)
            hx0, hy0 = getattr(b, "_fin_hero0", (640, 540))
            if t <= _FIN_REVEAL:                    # le héros s'élève et MUE
                u = max(0.0, min(1.0, t / float(_FIN_REVEAL))); ue = u * u * (3 - 2 * u)
                self.player.rect.center = (int(hx0 + (stance[0] - hx0) * ue),
                                           int(hy0 + (stance[1] - hy0) * ue - math.sin(ue * math.pi) * 46))
            else:
                self.player.rect.center = (stance[0], int(stance[1] + math.sin(t * 0.05) * 5))
            self.player.invuln = 999
            # Transformation VISUELLE : on mue le SPRITE RÉEL du héros en néant.
            self.player._void_form = (t >= _FIN_REVEAL - 120)
            self.player._void_u = min(1.0, max(0.0, (t - (_FIN_REVEAL - 120)) / 120.0))
            self._fin_camshake = getattr(self, "_fin_camshake", 0.0) * 0.88
            if t == _FIN_REVEAL - 1:                # éclat de révélation
                b._fin_revealed = True
                self.flash((180, 210, 255), 22)
                self.play_sfx("boss_explosion", 0.95)   # la mue détone
                burst(self.particles, stance[0], stance[1], 72, (210, 235, 255), 6.0, 50, 0.0, 6)
                self.projectiles_boss[:] = []       # l'éveil balaie la pluie figée

            # Voix scriptées (Aegis grave ; le héros = voix abyssale unique).
            if t == _FIN_SURPRISE: self._play_voice_line(_VOICE_AEGIS_VOID)
            if t == _FIN_QUESTION: self._play_voice_line(_VOICE_AEGIS_VOID)
            if t == _FIN_ANSWER:
                self._play_voice_line(_VOICE_HERO, n=5, gap=4)
                self.play_sfx("sword_cut", 1.0)         # « Je suis la fin. » — la sentence claque
                self.flash((230, 240, 255), 14)

            # ── LE DÉLUGE : tempête d'ÉNERGIE DE POINGS (façon Susano'o) ─────
            if _FIN_BARRAGE <= t < _FIN_ASH:
                tb = t - _FIN_BARRAGE
                p = tb / float(_FIN_ASH - _FIN_BARRAGE)        # 0 → 1 sur les ~17 s
                inten = min(1.0, tb / 220.0)
                b.float_offset += random.uniform(-4 - 8 * inten, 4 + 8 * inten)   # tremble
                if t % max(3, 7 - int(tb / 260)) == 0:                            # cendres qui se détachent
                    burst(self.particles, b.x + random.randint(-b.vis // 2, b.vis // 2),
                          b.y + random.randint(-b.vis // 2, b.vis // 2),
                          2 + int(3 * inten),
                          random.choice(((120, 120, 130), (92, 72, 80), _AEGIS_COL_DARK2)),
                          2.5, 46, -0.02, 4)
                # ÉNERGIE DE FOND OFFENSIVE : une onde de l'arène se RESSERRE sur Aegis
                # et le BRÛLE (elle FAIT partie de l'attaque). De + en + fréquente.
                self._fin_surge_T = max(22, 46 - int(p * 24))
                if tb % self._fin_surge_T == self._fin_surge_T - 1:
                    self._fin_camshake = max(self._fin_camshake, 15.0)
                    self._fin_hitstop = max(getattr(self, "_fin_hitstop", 0), 2)   # mini-gel d'impact
                    self.play_sfx("boss_hit", 0.7)      # l'énergie le frappe (rythme du tabassage)
                    b.float_offset += random.uniform(-24, 24)
                    burst(self.particles, b.x + random.randint(-b.vis // 2, b.vis // 2),
                          b.y + random.randint(-b.vis // 2, b.vis // 2),
                          24, random.choice(((150, 210, 255), (190, 225, 255), _AEGIS_COL_DARK2)),
                          7.5, 38, 0.0, 5)
                    burst(self.particles, b.x + random.randint(-b.vis // 2, b.vis // 2),
                          b.y + random.randint(-b.vis // 2, b.vis // 2),
                          12, random.choice(((44, 32, 50), (78, 60, 70), _AEGIS_COL_DARK)),
                          5.5, 46, 0.18, 5)            # DÉBRIS sombres arrachés au dieu
                # SPAWN de poings : ESCALADE sur toute la durée — de + en + nombreux
                # ET de + en + rapides (cadence qui s'emballe, vol plus court).
                rate = max(1, int(7 - 6 * p))                  # toutes les 7 frames → chaque frame
                if tb % rate == 0:
                    for _ in range(1 + int(p * 3.5)):          # 1 → 4 poings par salve
                        ang = random.uniform(0, math.tau); dist = random.uniform(380, 720)
                        dmin = max(7, int(22 - 14 * p)); dmax = max(dmin + 3, int(30 - 16 * p))  # vol + court = + rapide
                        self._fin_fists.append({
                            "x": b.x + math.cos(ang) * dist, "y": b.y + math.sin(ang) * dist,
                            "tx": b.x + random.uniform(-120, 120), "ty": b.y + random.uniform(-120, 70),
                            "t": 0, "dur": random.randint(dmin, dmax), "sc": random.uniform(0.9, 1.8)})
                if tb == 510:                                                     # POING COLOSSAL (climax)
                    self._fin_fists.append({"x": b.x, "y": b.y - 620, "tx": b.x, "ty": b.y,
                                            "t": 0, "dur": 36, "sc": 4.6, "giant": True})
                alive = []                                                        # avance les poings → impacts
                for f in self._fin_fists:
                    f["t"] += 1
                    if f["t"] >= f["dur"]:
                        big = f.get("giant", False)
                        self._fin_impacts.append({"x": f["tx"], "y": f["ty"], "t": 0,
                                                  "sc": f["sc"], "giant": big})
                        self._fin_camshake = max(self._fin_camshake, 26.0 if big else 9.0)
                        b.float_offset += random.uniform(-12, 12)      # le coup le secoue
                        if big:
                            self.flash((255, 238, 252), 12)   # seul le poing COLOSSAL flashe l'écran
                            self._fin_hitstop = max(getattr(self, "_fin_hitstop", 0), 7)
                            self.play_sfx("boss_explosion", 1.0)
                        burst(self.particles, f["tx"], f["ty"], 40 if big else 14,
                              (255, 242, 252), 9.0 if big else 5.2, 30, 0.0, 6)
                        burst(self.particles, f["tx"], f["ty"], 22 if big else 8,
                              random.choice(((44, 32, 50), (78, 60, 70), _AEGIS_COL_DARK)),
                              6.0 if big else 4.2, 46, 0.18, 5)        # DÉBRIS (morceaux du dieu)
                    else:
                        alive.append(f)
                self._fin_fists = alive
                for im in self._fin_impacts: im["t"] += 1
                self._fin_impacts = [im for im in self._fin_impacts if im["t"] < 28][-14:]
                for bt0 in (10, 160, 320, 480, 640, 790, 890):                    # répliques d'Aegis
                    if tb == bt0:
                        self._play_voice_line(_VOICE_AEGIS_VOID, n=3, gap=3)

            # ── CENDRES : le dieu se désintègre (au lieu d'être tranché) ──────
            if t == _FIN_ASH:
                b.dead = True; b.death_t = 999          # cache le sprite normal
                self.projectiles_boss[:] = []; self.beams[:] = []; self.rings[:] = []
                self.flash((255, 255, 255), 30)
                self.play_sfx("boss_explosion", 1.0)    # Aegis réduit en cendres
                burst(self.particles, b.x, b.y, 220, (180, 175, 185), 9.0, 90, 0.02, 7)
                burst(self.particles, b.x, b.y, 150, (120, 90, 95), 6.5, 80, 0.03, 6)
                burst(self.particles, b.x, b.y, 100, _AEGIS_COL_DARK2, 7.0, 70, 0.0, 6)
            if t > _FIN_ASH and t % 3 == 0:             # cendres résiduelles qui montent
                burst(self.particles, b.x + random.randint(-90, 90), b.y + random.randint(-60, 80),
                      2, random.choice(((150, 145, 155), (95, 75, 82))), 1.6, 70, -0.04, 3)
            if t >= _FIN_ASH_END:
                b.finale_act = "ending"; b.finale_t = 0

        elif act == "ending":
            if t == 1:
                self.player.score += 10000
            # Le héros erre lentement dans le néant.
            self.player.rect.centerx = 640 + int(150 * math.sin(t * 0.011))
            if t % 11 == 0:
                burst(self.particles, random.randint(0, WIDTH), random.randint(0, HEIGHT),
                      1, _AEGIS_COL_VOID, 0.6, 60, 0.0, 3)
            if t < 260 and t % 4 == 0:       # cendres résiduelles d'Aegis qui s'élèvent
                burst(self.particles, int(b.x) + random.randint(-110, 110),
                      int(b.y) + random.randint(-40, 90),
                      2, random.choice(((150, 145, 155), (95, 75, 82))), 1.4, 80, -0.05, 3)
            if t >= 900:
                self.finale_done = True      # débloque [R] pour revenir au titre

    # ── FINALE : rendu complet (le décor EST le néant) ──────────────────────
    def _draw_finale_world(self):
        b = self.boss; scr = self.screen; cam = self.cam; fr = self.frame
        # ── DAIS d'obsidienne flottant (seule la dalle principale est dessinée ;
        #    les parois sont des colliders invisibles). ──
        if self.platforms:
            slab = self.platforms[0].rect
            sx = int(slab.x - cam[0]); sy = int(slab.y - cam[1])
            ug = pygame.Surface((slab.w + 260, 150), pygame.SRCALPHA)
            pygame.draw.ellipse(ug, (150, 24, 116, 60), (0, 0, slab.w + 260, 150))
            scr.blit(ug, (sx - 130, sy + 24), special_flags=pygame.BLEND_RGBA_ADD)
            for k in range(slab.h):                          # corps en dégradé
                f = k / max(1, slab.h)
                col = (int(20 - 14 * f), int(9 - 6 * f), int(30 - 18 * f))
                pygame.draw.line(scr, col, (sx, sy + k), (sx + slab.w, sy + k))
            for fxp in range(sx + 70, sx + slab.w - 50, 120):  # veines de lumière
                pygame.draw.line(scr, (120, 28, 88), (fxp, sy + 10),
                                 (fxp + 16, sy + slab.h - 8), 1)
            glow = max(0, min(255, int(190 + 60 * math.sin(fr * 0.08))))
            pygame.draw.line(scr, (255, 90, 200), (sx, sy), (sx + slab.w, sy), 3)
            pygame.draw.line(scr, (255, 210, 240, glow)[:3], (sx, sy + 1), (sx + slab.w, sy + 1), 1)
        # Projectiles : les MÉTÉORITES de la survie ont leur propre rendu.
        for proj in self.projectiles_boss:
            if getattr(proj, "kind", "") == "meteor":
                self._draw_meteor(scr, proj.x - cam[0], proj.y - cam[1], proj.radius * 1.15,
                                  fr, getattr(proj, "vx", 0.0), getattr(proj, "vy", 1.0))
            else:
                proj.draw(scr, cam)
        for rg in self.rings: rg.draw(scr, cam)
        # Aegis — rendu DÉDIÉ (splat-art net, pas le halo délavé du combat).
        if not (b.dead and b.death_t > 90):
            self._draw_finale_aegis(scr, int(b.x - cam[0]), int(b.y + b.float_offset - cam[1]))
        # Héros (toujours solide, jamais clignotant).
        if self.player:
            _sav = self.player.invuln; self.player.invuln = 0
            self.player.draw(scr, cam); self.player.invuln = _sav
        for part in self.particles: part.draw(scr, cam)
        self._draw_finale()

    def _draw_finale_aegis(self, scr, cx, cy):
        """Rendu DÉDIÉ d'Aegis dans le néant : le vrai splat-art, NET, sublimé
        (nébuleuse douce + aiguilles de lumière + yeux-étoiles), sans le halo
        délavé du combat qui le blanchissait."""
        b = self.boss; vis = b.vis; fr = self.frame
        # 1) Halo doux en DÉGRADÉ lisse (auréole contenue, pas un disque plat).
        side = vis * 4; c = side // 2
        neb = pygame.Surface((side, side), pygame.SRCALPHA)
        for k in range(18):
            rr = int(vis * (1.95 - k * 0.10))
            if rr <= 0: continue
            pygame.draw.circle(neb, (120, 16, 96, 4), (c, c), rr)
        scr.blit(neb, (cx - c, cy - c), special_flags=pygame.BLEND_RGBA_ADD)
        # 2) Fines aiguilles de lumière rayonnant derrière (le « soleil noir »).
        n = 16
        for i in range(n):
            a = i * math.tau / n + b.bob_t * 0.12
            l1 = vis * 0.95; l2 = vis * (1.5 + 0.12 * math.sin(b.bob_t * 1.1 + i))
            pygame.draw.line(scr, (190, 46, 142),
                             (int(cx + math.cos(a) * l1), int(cy + math.sin(a) * l1)),
                             (int(cx + math.cos(a) * l2), int(cy + math.sin(a) * l2)), 2)
        # 3) LE SPRITE splat-art (forme dark), NET.
        sheet = getattr(self, "_aegis_sheet_dark", None) or getattr(self, "_aegis_sheet", None)
        if sheet:
            fw = self._aegis_frame_w; nf = max(1, sheet.get_width() // fw)
            fi = (b._anim_t // 4) % nf
            try:
                frame = sheet.subsurface((fi * fw, 0, fw, sheet.get_height()))
            except Exception:
                frame = sheet.subsurface((0, 0, fw, sheet.get_height()))
            scaled = pygame.transform.scale(frame, (vis * 2, vis * 2))
            scr.blit(scaled, (cx - vis, cy - vis))
        else:
            pygame.draw.circle(scr, _AEGIS_COL_DARK, (cx, cy), b.radius)
        # 4) Yeux-étoiles ROUGES (alignés sur le visage, comme COURROUX).
        eyo = int(vis * 0.28)
        er = 11 + 4 * math.sin(fr * 0.3)
        for sgn in (-1, 1):
            self._blit_star(scr, cx + sgn * eyo, cy - eyo, er * 2.2, er * 0.9,
                            (255, 30, 30), glow=(255, 90, 60), a=235, rot=fr * 0.04)

    def _draw_god_halves(self, scr, cx, cy, sep, alpha=255):
        """Coupe le SPRITE splat-art en deux moitiés qui s'écartent (vrai dieu
        tranché, pas de vagues ellipses)."""
        vis = self.boss.vis
        sheet = getattr(self, "_aegis_sheet_dark", None) or getattr(self, "_aegis_sheet", None)
        if not sheet:
            return
        try:
            frame = sheet.subsurface((0, 0, self._aegis_frame_w, sheet.get_height()))
        except Exception:
            return
        scaled = pygame.transform.scale(frame, (vis * 2, vis * 2))
        lh = scaled.subsurface((0, 0, vis, vis * 2)).copy()
        rh = scaled.subsurface((vis, 0, vis, vis * 2)).copy()
        a = max(0, min(255, int(alpha)))
        lh.set_alpha(a); rh.set_alpha(a)
        scr.blit(lh, (cx - vis - sep, cy - vis))
        scr.blit(rh, (cx + sep, cy - vis))

    def _taper_poly(self, spine, base_w, tip_w):
        """Construit un polygone EFFILÉ qui suit une courbe (spine) : largeur
        base_w à la base → tip_w à la pointe. Donne des serres organiques."""
        n = len(spine)
        if n < 2: return [(int(x), int(y)) for x, y in spine]
        top = []; bot = []
        for i in range(n):
            x, y = spine[i]
            u = i / (n - 1.0)
            w = base_w * (1 - u) + tip_w * u
            if i < n - 1: dx, dy = spine[i + 1][0] - x, spine[i + 1][1] - y
            else:         dx, dy = x - spine[i - 1][0], y - spine[i - 1][1]
            d = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / d, dx / d
            top.append((x + nx * w, y + ny * w)); bot.append((x - nx * w, y - ny * w))
        return [(int(x), int(y)) for x, y in (top + bot[::-1])]

    def _draw_claw_hand(self, surf, tipx, cy, dirx, scale=1.0):
        """GRIFFE colossale d'Aegis : 4 grosses serres COURBES (crochets) émergeant
        du bord, reliées par une racine sombre, qui agrippent la couture en tipx.
        Remplissage VISIBLE + fort rétro-éclairage + arêtes & pointes dorées."""
        s = scale
        reach = int(370 * s)
        root_x = int(tipx - dirx * reach)
        rw = int(150 * s); rh = int(160 * s)
        # Spines des 4 serres (crochets — Bézier qui s'incurvent vers la pointe).
        spines = []
        for i in range(4):
            tt = (i - 1.5) / 1.5
            b0 = (root_x + dirx * 26 * s, cy + tt * rh * 0.78)
            tip = (tipx, cy + tt * 28 * s)
            mid = (b0[0] + dirx * reach * 0.55, b0[1] + tt * 30 * s - 40 * s)  # crochet
            sp = []
            for k in range(11):
                u = k / 10.0
                qx = (1 - u) ** 2 * b0[0] + 2 * (1 - u) * u * mid[0] + u * u * tip[0]
                qy = (1 - u) ** 2 * b0[1] + 2 * (1 - u) * u * mid[1] + u * u * tip[1]
                sp.append((qx, qy))
            spines.append(sp)
        # 1) RÉTRO-ÉCLAIRAGE fort (halo magenta derrière la griffe).
        gl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(gl, (185, 30, 130, 95),
                            (root_x - dirx * rw - (rw if dirx < 0 else 0), cy - rh, rw * 2, rh * 2))
        for sp in spines:
            pygame.draw.lines(gl, (200, 36, 140, 90), False,
                              [(int(x), int(y)) for x, y in sp], max(10, int(24 * s)))
        surf.blit(gl, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        # 2) RACINE sombre (le poignet d'où sortent les serres).
        root = [(root_x - dirx * rw, cy - rh), (root_x + dirx * 30 * s, cy - rh * 0.7),
                (root_x + dirx * 30 * s, cy + rh * 0.7), (root_x - dirx * rw, cy + rh)]
        pygame.draw.polygon(surf, (40, 13, 32), root)
        pygame.draw.polygon(surf, (205, 46, 128), root, 3)
        # 3) Les SERRES : remplissage visible + arête vive + pointe dorée.
        for sp in spines:
            poly = self._taper_poly(sp, int(32 * s), 2)
            pygame.draw.polygon(surf, (50, 16, 38), poly)                 # chair VISIBLE
            pygame.draw.polygon(surf, (214, 50, 134), poly, max(2, int(3 * s)))
            pygame.draw.lines(surf, (255, 124, 206), False,              # reflet sur l'arête
                              [(int(x), int(y)) for x, y in sp], max(1, int(2 * s)))
            pygame.draw.lines(surf, (248, 206, 116), False,             # pointe dorée
                              [(int(x), int(y)) for x, y in sp[-4:]], max(3, int(7 * s)))

    def _draw_finale(self):
        act = self.boss.finale_act
        if act == "prelude":    self._draw_finale_prelude()
        elif act == "dialogue": self._draw_finale_dialogue()
        elif act == "survival": self._draw_finale_survival()
        elif act == "timestop": self._draw_finale_timestop()
        elif act == "ending":   self._draw_finale_ending()

    def _fin_textbox(self, speaker_col, txt, alpha=255, speaker=None):
        """Boîte de dialogue lisible en bas (caisson + ombre + nom + fondu)."""
        scr = self.screen; W, H = WIDTH, HEIGHT
        alpha = max(0, min(255, int(alpha)))
        if alpha <= 0: return
        s = self.font_med.render(txt, True, speaker_col)
        sh = self.font_med.render(txt, True, (14, 2, 22))
        bw = s.get_width() + 64; bh = s.get_height() + 28
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        box.fill((5, 1, 10, int(238 * alpha / 255)))
        pygame.draw.rect(box, (170, 34, 116, alpha), box.get_rect(), 2)
        br = box.get_rect(center=(W // 2, H - 74)); scr.blit(box, br)
        if speaker:
            nm = self.font_sm.render(speaker, True, (255, 110, 200))
            nm.set_alpha(alpha)
            scr.blit(nm, nm.get_rect(midleft=(br.left + 6, br.top - 12)))
        s.set_alpha(alpha); sh.set_alpha(alpha)
        r = s.get_rect(center=(W // 2, H - 74))
        scr.blit(sh, (r.x + 2, r.y + 2)); scr.blit(s, r)

    def _draw_finale_prelude(self):
        scr = self.screen; W, H = WIDTH, HEIGHT; t = self.boss.finale_t

        def ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)

        TEAR = _FIN_TEAR  # l'arrachage par les mains (la fissure se forme TRÈS lentement avant)
        OPEN = _FIN_OPEN  # écart complet
        # Secousse d'écran : surgissement des mains, puis arrachage.
        shake_amp = 0.0
        for (st0, sa0, sd) in ((_FIN_HANDS, 16, 90), (TEAR, 10, 60)):
            if st0 <= t < st0 + sd:
                shake_amp = max(shake_amp, sa0 * (1 - (t - st0) / float(sd)))
        if t < TEAR:   slide = 0.0
        elif t < OPEN: slide = ease((t - TEAR) / float(OPEN - TEAR)) * (W / 2 + 140)
        else:          slide = W / 2 + 160
        seam_l = int(W / 2 - slide); seam_r = int(W / 2 + slide)
        # Voiles (= l'ancien écran de fin, noir) qui s'écartent.
        if slide < W / 2 + 150:
            if seam_l + 12 > 0:
                lv = pygame.Surface((seam_l + 12, H)); lv.fill((4, 1, 8)); scr.blit(lv, (0, 0))
            if W - seam_r + 12 > 0:
                rv = pygame.Surface((W - seam_r + 12, H)); rv.fill((4, 1, 8)); scr.blit(rv, (seam_r - 12, 0))
            if t < 210:
                a = max(0, int(190 * (1 - t / 210.0)))
                s = self.font_med.render("...Incroyable.", True, (200, 160, 255)); s.set_alpha(a)
                scr.blit(s, s.get_rect(center=(W // 2, H // 2)))
        # Fissure DÉCHIQUETÉE incandescente (tracé stable + lueur en couches).
        def _jag(xc, y0, y1, amp):
            random.seed(int(xc) * 31 + 7)
            pts = [(xc, y0)]; yy = y0 + 22
            while yy < y1:
                pts.append((int(xc + random.randint(-amp, amp)), yy)); yy += 22
            pts.append((xc, y1)); random.seed()
            return pts
        if slide < 6:
            # FORMATION PROGRESSIVE (0→TEAR) : naît d'un point, s'étire lentement.
            prog = ease(t / float(TEAR))
            gh = int(40 + 560 * prog); amp = int(3 + 14 * prog)
            y0 = H // 2 - gh // 2; y1 = H // 2 + gh // 2
            jag = _jag(W // 2, y0, y1, amp)
            pygame.draw.lines(scr, (110, 8, 64), False, jag, max(5, int(12 * prog)))
            pygame.draw.lines(scr, (255, 90, 205), False, jag, max(2, int(6 * prog)))
            pygame.draw.lines(scr, (255, 244, 252), False, jag, max(1, int(3 * prog)))
            if prog > 0.4:                          # ramifications qui apparaissent
                random.seed(13)
                for _ in range(int(7 * prog)):
                    by_ = random.randint(y0, y1); bx_ = W // 2 + random.randint(-amp, amp)
                    ba = random.choice((-1, 1))
                    pygame.draw.line(scr, (255, 110, 215), (bx_, by_),
                                     (bx_ + ba * int(46 * prog), by_ + random.randint(-22, 22)), 2)
                random.seed()
            for _ in range(int(7 * prog)):          # étincelles
                sy = random.randint(y0, y1)
                pygame.draw.circle(scr, (255, 185, 232),
                                   (W // 2 + random.randint(-amp - 8, amp + 8), sy), random.randint(1, 3))
            hr = int(18 + 86 * prog)                # halo central : la pression monte
            hs = pygame.Surface((hr * 2 + 8, hr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(hs, (180, 30, 130, int(64 * prog)), (hr + 4, hr + 4), hr)
            scr.blit(hs, (W // 2 - hr - 4, H // 2 - hr - 4), special_flags=pygame.BLEND_RGBA_ADD)
        elif seam_r > seam_l:
            # L'écart révèle le néant : gerbe de lumière + bords déchiquetés ardents.
            fl = pygame.Surface((seam_r - seam_l, H), pygame.SRCALPHA)
            for k in range(0, H, 5):
                pygame.draw.line(fl, (255, 120, 220, random.randint(12, 66)),
                                 (0, k), (fl.get_width(), k), 2)
            scr.blit(fl, (seam_l, 0), special_flags=pygame.BLEND_RGBA_ADD)
            for seam in (seam_l, seam_r):
                jag = _jag(seam, 0, H, 8)
                pygame.draw.lines(scr, (110, 8, 64), False, jag, 9)
                pygame.draw.lines(scr, (255, 110, 215), False, jag, 4)
                pygame.draw.lines(scr, (255, 244, 252), False, jag, 1)
        # LES MAINS du dieu : SPAWN animé (surgissent + grossissent), puis tirent.
        if _FIN_HANDS <= t < _FIN_PRELUDE_END:
            grow = min(1.0, (t - _FIN_HANDS) / 60.0)
            hs = 0.55 + 0.45 * grow
            self._draw_claw_hand(scr, seam_l, H // 2, +1, hs)
            self._draw_claw_hand(scr, seam_r, H // 2, -1, hs)
        # Cri d'Aegis (pendant l'arrachage).
        if t >= TEAR:
            a = min(255, int((t - TEAR) * 6))
            if t > _FIN_PRELUDE_END - 80: a = max(0, 255 - int((t - (_FIN_PRELUDE_END - 80)) * 5))
            if a > 0:
                line = self.font_big.render("NON. On n'efface pas l'éternel.", True, (255, 50, 50))
                sh = self.font_big.render("NON. On n'efface pas l'éternel.", True, (40, 0, 0))
                line.set_alpha(a); sh.set_alpha(a)
                r = line.get_rect(center=(W // 2, H // 2 - 150))
                scr.blit(sh, (r.x + 3, r.y + 3)); scr.blit(line, r)
        if t < 24:
            fo = pygame.Surface((W, H)); fo.fill((0, 0, 0)); fo.set_alpha(int(255 * (1 - t / 24.0)))
            scr.blit(fo, (0, 0))
        # Secousse : on décale toute l'image (les mains arrachent le réel).
        if shake_amp > 0.5:
            snap = scr.copy(); scr.fill((4, 1, 8))
            scr.blit(snap, (int(random.uniform(-shake_amp, shake_amp)),
                            int(random.uniform(-shake_amp, shake_amp))))

    def _draw_finale_dialogue(self):
        """Dialogue en répliques SÉQUENTIELLES (plus de clignotement) avec fondu."""
        t = self.boss.finale_t
        MAG = (255, 160, 228); SIL = (215, 215, 235)

        def beat(t0, t1, col, txt, speaker):
            if not (t0 <= t < t1): return
            a = 255
            if t < t0 + 18: a = int(255 * (t - t0) / 18)
            elif t > t1 - 20: a = int(255 * (t1 - t) / 20)
            self._fin_textbox(col, txt, alpha=a, speaker=speaker)

        # 6 répliques nettes, une à la fois (Aegis ↔ silence du héros).
        beat(0,    200,  MAG, "Mon royaume. Ici, je suis TOUT.",                   "AEGIS")
        beat(200,  430,  MAG, "Tu n'as plus rien. Plus d'arc, plus de rêve. Juste... toi.", "AEGIS")
        beat(430,  610,  SIL, "« ... »",                                            None)
        beat(610,  830,  MAG, "Pourquoi ce silence ?! DIS QUELQUE CHOSE !",         "AEGIS")
        beat(830,  1000, SIL, "« ... »",                                            None)
        beat(1000, 1140, MAG, "...Soit. Je vais te l'arracher.",                    "AEGIS")

    def _draw_finale_survival(self):
        scr = self.screen; W, H = WIDTH, HEIGHT; fr = self.frame
        g = self.finale_gauge
        # Vignette rouge pulsée (oppression du néant).
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vg, (120, 0, 30, 70 + int(20 * math.sin(fr * 0.1))), (0, 0, W, H), 130)
        scr.blit(vg, (0, 0))
        # Réplique d'Aegis qui perd pied (selon la progression).
        line = None
        if g < 0.30:   line = "pourquoi... tu ne tombes pas ?"
        elif g < 0.65: line = "qu'est-ce que tu ES ?!"
        elif g < 0.95: line = "ARRÊTE de te relever !"
        if line:
            s = self.font_sm.render(line, True, (255, 140, 200))
            scr.blit(s, s.get_rect(center=(W // 2, 70)))
        # Jauge « ?! » en bas-centre.
        bw, bh = 360, 22; bx = W // 2 - bw // 2; by = H - 64
        pygame.draw.rect(scr, (8, 2, 12), (bx - 3, by - 3, bw + 6, bh + 6), border_radius=5)
        fillw = int(bw * g)
        col = (255, 90, 200) if g < 1.0 else (255, 230, 120)
        if fillw > 0:
            pygame.draw.rect(scr, col, (bx, by, fillw, bh), border_radius=4)
        pygame.draw.rect(scr, (150, 40, 110), (bx, by, bw, bh), 2, border_radius=4)
        if g < 1.0:
            lab = self.font_sm.render("?!", True, (230, 180, 220))
            scr.blit(lab, lab.get_rect(center=(W // 2, by - 18)))
        else:
            pulse = 0.5 + 0.5 * math.sin(fr * 0.25)
            big = self.font_big.render("?!", True, (255, int(200 + 55 * pulse), 120))
            scr.blit(big, big.get_rect(center=(W // 2, by - 40)))
            hint = self.font_sm.render("[ CLIC ]", True, (255, int(180 + 60 * pulse), 120))
            scr.blit(hint, hint.get_rect(center=(W // 2, by - 8)))

    def _draw_meteor(self, scr, cx, cy, R, fr, vx=0.0, vy=1.0):
        """Météorite (réutilisée de COURROUX) : traînée de feu + roche sombre +
        rim incandescent crénelé."""
        R = max(4, int(R)); cx = int(cx); cy = int(cy)
        sp = math.hypot(vx, vy) or 1.0
        tdx, tdy = -vx / sp, -vy / sp                # traînée à l'opposé du mouvement
        for k in range(1, 7):
            rr = max(2, int(R * (1 - k * 0.13)))
            ts = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ts, (255, 120, 50, max(0, 120 - k * 18)), (rr + 2, rr + 2), rr)
            scr.blit(ts, (int(cx + tdx * k * R * 0.7) - rr - 2, int(cy + tdy * k * R * 0.7) - rr - 2),
                     special_flags=pygame.BLEND_RGBA_ADD)
        ms = pygame.Surface((R * 4, R * 4), pygame.SRCALPHA); c = R * 2
        for k in range(5):
            pygame.draw.circle(ms, (255, 110, 40, max(0, 48 - k * 9)), (c, c), int(R * (1.55 - k * 0.16)))
        for k in range(5):
            pygame.draw.circle(ms, (38, 12, 16) if k == 0 else (74, 26, 30), (c, c), int(R * (1.0 - k * 0.16)))
        gl = max(0, min(255, int(175 + 70 * math.sin(fr * 0.3))))
        pygame.draw.circle(ms, (255, 150, 70, gl), (c, c), R, 3)
        for i in range(10):
            a = i * math.tau / 10 + fr * 0.04
            pygame.draw.line(ms, (110, 40, 36),
                             (c + int(math.cos(a) * R * 0.82), c + int(math.sin(a) * R * 0.82)),
                             (c + int(math.cos(a) * R * 1.05), c + int(math.sin(a) * R * 1.05)), 2)
        scr.blit(ms, (cx - c, cy - c))

    def _draw_light_blade(self, scr, hx, hy, ang, L, glow=1.0):
        """BELLE lame de lumière : garde dorée + lame effilée (cœur blanc, tranchant
        lumineux), halo additif doux, pointe étincelante."""
        W, H = WIDTH, HEIGHT
        hx, hy = int(hx), int(hy)
        cosA, sinA = math.cos(ang), math.sin(ang)
        pxv, pyv = -sinA, cosA                       # perpendiculaire (largeur)
        base = (hx + cosA * 20, hy + sinA * 20)      # juste après la garde
        tip = (hx + cosA * L, hy + sinA * L)
        midx, midy = hx + cosA * L * 0.5, hy + sinA * L * 0.5
        # 1) HALO additif (doux, large).
        gl = pygame.Surface((W, H), pygame.SRCALPHA)
        gw = 7 + 9 * glow
        pygame.draw.polygon(gl, (210, 60, 175, int(110 * glow)),
                            [(base[0] + pxv * gw, base[1] + pyv * gw), tip,
                             (base[0] - pxv * gw, base[1] - pyv * gw)])
        scr.blit(gl, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        # 2) CORPS de lame (losange effilé) blanc-rosé.
        w = 4 + 2 * glow
        body = [(base[0] + pxv * w, base[1] + pyv * w),
                (midx + pxv * w * 0.7, midy + pyv * w * 0.7), tip,
                (midx - pxv * w * 0.7, midy - pyv * w * 0.7),
                (base[0] - pxv * w, base[1] - pyv * w)]
        pygame.draw.polygon(scr, (255, 205, 242), [(int(x), int(y)) for x, y in body])
        # 3) Tranchant + cœur blanc-chaud.
        pygame.draw.line(scr, (255, 160, 225), (int(base[0] + pxv * w), int(base[1] + pyv * w)),
                         (int(tip[0]), int(tip[1])), 1)
        pygame.draw.line(scr, (255, 255, 255), (int(base[0]), int(base[1])),
                         (int(tip[0]), int(tip[1])), 2)
        # 4) GARDE dorée (crossguard) + pommeau.
        g = 17
        pygame.draw.line(scr, (245, 205, 120), (int(hx - pxv * g), int(hy - pyv * g)),
                         (int(hx + pxv * g), int(hy + pyv * g)), 5)
        pygame.draw.circle(scr, (245, 205, 120), (int(hx - cosA * 9), int(hy - sinA * 9)), 4)
        # 5) Pointe étincelante (étoile).
        pygame.draw.circle(scr, (255, 255, 255), (int(tip[0]), int(tip[1])), max(3, int(4 * glow)))
        for k in range(4):
            aa = ang + k * math.pi / 2; spk = 7 + 5 * glow
            pygame.draw.line(scr, (255, 232, 250), (int(tip[0]), int(tip[1])),
                             (int(tip[0] + math.cos(aa) * spk), int(tip[1] + math.sin(aa) * spk)), 1)

    def _apply_finale_cam(self, scr, t, bx, by, px, py):
        """CAMÉRA de l'exécution : gel → gros plan Aegis surpris → bascule sur la
        VRAIE FORME du héros → face-à-face → large sur le déluge → punch des cendres."""
        W, H = WIDTH, HEIGHT
        def ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)
        face = (bx, by - int(self.boss.vis * 0.30))
        mid = ((bx + px) // 2, (by + py) // 2)
        kf = [
            (0,                640, 360, 1.00),            # large : le néant gelé
            (_FIN_SURPRISE,    face[0], face[1], 1.85),    # GROS PLAN : Aegis réalise
            (_FIN_REVEAL,      px, py, 1.75),              # bascule sur le héros qui MUE
            (_FIN_REVEAL + 120, px, py, 1.55),
            (_FIN_QUESTION,    mid[0], mid[1], 1.40),      # face-à-face
            (_FIN_ANSWER,      px, py, 1.70),              # « Je suis la fin. »
            (_FIN_BARRAGE,     640, 360, 1.06),            # large : on voit le déluge
            (_FIN_ASH - 60,    640, 360, 1.06),
            (_FIN_ASH,         bx, by, 1.70),              # punch sur le dieu → cendres
            (_FIN_ASH + 90,    bx, by, 1.50),
            (_FIN_ASH_END,     640, 360, 1.00),            # large final
        ]
        fx, fy, zoom = 640, 360, 1.0
        for i in range(len(kf) - 1):
            t0, fx0, fy0, z0 = kf[i]; t1, fx1, fy1, z1 = kf[i + 1]
            if t0 <= t <= t1:
                e = ease((t - t0) / float(max(1, t1 - t0)))
                fx = fx0 + (fx1 - fx0) * e; fy = fy0 + (fy1 - fy0) * e
                zoom = z0 + (z1 - z0) * e; break
        # Secousses : impacts des poings (synchro) + smash des cendres.
        cs = getattr(self, "_fin_camshake", 0.0)
        if cs > 0.5:
            fx += random.uniform(-cs, cs); fy += random.uniform(-cs, cs)
        if _FIN_ASH <= t < _FIN_ASH + 60:
            amp = 18 * (1 - (t - _FIN_ASH) / 60.0)
            fx += random.uniform(-amp, amp); fy += random.uniform(-amp, amp)
        if zoom > 1.01:
            sw = max(2, int(W / zoom)); sh = max(2, int(H / zoom))
            sx = max(0, min(W - sw, int(fx) - sw // 2)); sy = max(0, min(H - sh, int(fy) - sh // 2))
            sub = scr.subsurface(pygame.Rect(sx, sy, sw, sh))
            scr.blit(pygame.transform.scale(sub.copy(), (W, H)), (0, 0))

    def _draw_energy_fist(self, fld, x, y, ang, sc, glow=1.0):
        """Un POING d'énergie (paume + 4 phalanges + traînée) dessiné en additif."""
        x, y = int(x), int(y)
        ca, sa = math.cos(ang), math.sin(ang); px, py = -sa, ca
        R = max(3, int(13 * sc)); a = max(0, min(230, int(165 * glow)))
        for k in range(1, 6):                         # traînée de comète derrière
            tx = int(x - ca * k * R * 0.7); ty = int(y - sa * k * R * 0.7)
            rr = max(1, int(R * (1 - k * 0.16)))
            pygame.draw.circle(fld, (130, 210, 255, max(0, a - k * 28)), (tx, ty), rr)
        pygame.draw.circle(fld, (120, 200, 255, a), (x, y), R)                 # paume
        pygame.draw.circle(fld, (255, 255, 255, min(255, a + 70)), (x, y), max(1, int(R * 0.52)))
        for kk in (-1.4, -0.5, 0.5, 1.4):             # 4 phalanges sur l'avant
            fxp = int(x + ca * R * 0.9 + px * kk * R * 0.55)
            fyp = int(y + sa * R * 0.9 + py * kk * R * 0.55)
            pygame.draw.circle(fld, (205, 242, 255, min(255, a + 30)), (fxp, fyp), max(1, int(R * 0.34)))

    def _draw_barrage(self, scr, tb, bx, by):
        """DÉLUGE d'ÉNERGIE DE POINGS (façon Susano'o) : fond d'énergie qui ondule
        + pluie chaotique de poings + ondes d'impact. Fluide, dense, brutal."""
        W, H = WIDTH, HEIGHT; fr = self.frame
        inten = min(1.0, tb / 200.0); ramp = 0.55 + 0.45 * min(1.0, tb / 820.0)
        period = getattr(self, "_fin_surge_T", 40); ph = tb % period
        cl = 1.0 - ph / float(period)                 # onde de fond : 1 (loin) → 0 (sur Aegis)
        surge = 1.0 + 0.8 * (1 - cl)                  # les rais FLAMBENT quand l'onde se referme
        bg = pygame.Surface((W, H), pygame.SRCALPHA); bg.fill((5, 1, 9, 86))
        scr.blit(bg, (0, 0))
        fld = pygame.Surface((W, H), pygame.SRCALPHA)
        # 1) FOND OFFENSIF : RAIS convergents qui FLAMBENT par vagues (concentration
        #    « anime »), + une onde qui se resserre sur Aegis et le BRÛLE.
        nray = 52
        for i in range(nray):
            a0 = i * math.tau / nray + fr * 0.012
            r0 = 96 + 46 * (0.5 + 0.5 * math.sin(fr * 0.07 + i * 1.7))    # bord intérieur pulsé
            r1 = 840
            aa = max(0, min(195, int((30 + 56 * inten) * ramp * surge) - (i * 53 % 6) * 5))
            x1 = bx + math.cos(a0) * r0; y1 = by + math.sin(a0) * r0
            x2 = bx + math.cos(a0) * r1; y2 = by + math.sin(a0) * r1
            pygame.draw.line(fld, (155, 218, 255, aa), (x1, y1), (x2, y2), 3 if i % 4 == 0 else 2)
        # 1b) ONDE qui se RESSERRE sur le dieu + brûlure focale à l'impact.
        cr = int(740 * cl)
        if cr > 8:
            sa_ = max(0, min(205, int(40 + 165 * (1 - cl))))
            pygame.draw.circle(fld, (180, 225, 255, sa_), (bx, by), cr, max(2, int(2 + 5 * (1 - cl))))
        if ph >= period - 7:
            bf = (period - ph) / 7.0
            pygame.draw.circle(fld, (215, 240, 255, int(130 * bf)), (bx, by), int(38 + (1 - bf) * 80))
        cglow = max(0, int(60 + 55 * math.sin(fr * 0.3)))   # noyau qui traverse Aegis
        pygame.draw.circle(fld, (150, 210, 255, cglow), (bx, by), int(30 + 12 * inten))
        # FRACTURES d'énergie : le dieu se FEND de + en + (brutalité croissante).
        pp = min(1.0, tb / float(_FIN_ASH - _FIN_BARRAGE)); rng = random.Random(7)
        for i in range(int(pp * 10)):
            a0 = rng.uniform(0, math.tau); seglen = rng.uniform(26, 50 + pp * 110)
            cx2, cy2 = float(bx), float(by); seg = [(bx, by)]
            for _s in range(3):
                a0 += rng.uniform(-0.55, 0.55)
                cx2 += math.cos(a0) * seglen / 3; cy2 += math.sin(a0) * seglen / 3
                seg.append((int(cx2), int(cy2)))
            pygame.draw.lines(fld, (215, 240, 255, 160), False, seg, 2)
        # 2) ONDES D'IMPACT (anneaux de choc qui s'étendent).
        for im in getattr(self, "_fin_impacts", []):
            d = im["t"]; big = im.get("giant", False); sc = im.get("sc", 1.0)
            ix, iy = int(im["x"] - self.cam[0]), int(im["y"] - self.cam[1])
            if d < 6:                                  # ÉCLAT LOCAL (au lieu d'un flash plein écran)
                f = (6 - d) / 6.0
                cr = int((26 if big else 12) * sc * (0.7 + d * 0.3))
                pygame.draw.circle(fld, (255, 255, 255, int((82 if big else 22) * f)), (ix, iy), max(1, cr))
                pygame.draw.circle(fld, (200, 235, 255, int((52 if big else 15) * f)), (ix, iy), max(1, int(cr * 1.7)))
            rr = int(d * (26 if big else 11) * (0.6 + 0.4 * sc))
            aa = max(0, int((235 if big else 165) - d * 12))
            if aa > 0 and rr > 0:
                col = (255, 255, 255) if d < 4 else (200, 240, 255)
                pygame.draw.circle(fld, (*col, aa), (ix, iy), rr, max(2, (7 if big else 2)))
                if big:
                    pygame.draw.circle(fld, (255, 200, 245, max(0, aa - 40)), (ix, iy), int(rr * 0.6), 4)
        # 3) POINGS en vol (trajectoire accélérée vers Aegis).
        for f in getattr(self, "_fin_fists", []):
            u = min(1.0, f["t"] / float(f["dur"])); ue = u * u
            cx = f["x"] + (f["tx"] - f["x"]) * ue - self.cam[0]
            cy = f["y"] + (f["ty"] - f["y"]) * ue - self.cam[1]
            ang = math.atan2(f["ty"] - f["y"], f["tx"] - f["x"])
            self._draw_energy_fist(fld, cx, cy, ang, f["sc"] * (0.7 + 0.3 * u), ramp)
        scr.blit(fld, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_namecard(self, scr, d):
        """Carte-titre « LA FIN » figée (façon « DEATH » de Susano'o) : sceau +
        cut de couleur + léger zoom."""
        W, H = WIDTH, HEIGHT
        a = min(255, int(d * 12))
        if d > 90: a = max(0, 255 - int((d - 90) * 8))
        if a <= 0: return
        band = pygame.Surface((W, H), pygame.SRCALPHA); band.fill((10, 0, 6, int(150 * a / 255)))
        scr.blit(band, (0, 0))
        cx, cy = W // 2, H // 2
        col = (255, 60, 70) if (d // 6) % 2 == 0 else (255, 232, 240)
        R = int(150 + 26 * min(1.0, d / 30.0))
        em = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(em, (*col, a), (R + 4, R + 4), R, 4)
        pygame.draw.circle(em, (*col, a), (R + 4, R + 4), int(R * 0.7), 2)
        pygame.draw.line(em, (*col, a), (R + 4, 8), (R + 4, R * 2), 3)
        pygame.draw.line(em, (*col, a), (8, R + 4), (R * 2, R + 4), 3)
        scr.blit(em, (cx - R - 4, cy - R - 4), special_flags=pygame.BLEND_RGBA_ADD)
        scale = 1.0 + 0.25 * min(1.0, d / 24.0)
        base = self.font_big.render("LA FIN", True, (255, 240, 245))
        bw = max(1, int(base.get_width() * scale)); bh = max(1, int(base.get_height() * scale))
        big = pygame.transform.smoothscale(base, (bw, bh))
        sh = pygame.transform.smoothscale(self.font_big.render("LA FIN", True, (60, 0, 14)), (bw, bh))
        big.set_alpha(a); sh.set_alpha(a)
        r = big.get_rect(center=(cx, cy))
        scr.blit(sh, (r.x + 4, r.y + 4)); scr.blit(big, r)

    def _draw_finale_timestop(self):
        scr = self.screen; W, H = WIDTH, HEIGHT; t = self.boss.finale_t; b = self.boss
        cam = self.cam; fr = self.frame
        bx = int(b.x - cam[0]); by = int(b.y + b.float_offset - cam[1])
        px = int(self.player.rect.centerx - cam[0]); py = int(self.player.rect.centery - cam[1])

        # ═════════ COUCHE MONDE (capturée par la CAMÉRA) ═════════
        # 1) GEL froid (se dissipe quand le déluge commence).
        gel = 1.0 if t < _FIN_BARRAGE else max(0.0, 1.0 - (t - _FIN_BARRAGE) / 90.0)
        if gel > 0:
            fz = pygame.Surface((W, H), pygame.SRCALPHA); fz.fill((70, 88, 150, int(70 * gel)))
            scr.blit(fz, (0, 0))
        if t < 42:                                        # onde de gel initiale
            rr = int(t * 36)
            rs = pygame.Surface((rr * 2 + 8, rr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(rs, (220, 235, 255, max(0, 190 - t * 4)), (rr + 4, rr + 4), rr, 7)
            scr.blit(rs, (px - rr - 4, py - rr - 4), special_flags=pygame.BLEND_RGBA_ADD)
        # 2) AEGIS SURPRIS : onde de choc d'effroi.
        if _FIN_SURPRISE <= t < _FIN_SURPRISE + 40:
            d = t - _FIN_SURPRISE; rr = int(d * 9)
            sw = pygame.Surface((rr * 2 + 8, rr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(sw, (255, 60, 60, max(0, 170 - d * 4)), (rr + 4, rr + 4), rr, 5)
            scr.blit(sw, (bx - rr - 4, by - rr - 4), special_flags=pygame.BLEND_RGBA_ADD)
        # 3) (La VRAIE FORME du héros est dessinée par le sprite lui-même via
        #     Player._draw_void, dans _draw_finale_world : sprite réel mué en néant.)
        # 4) LE DÉLUGE.
        if _FIN_BARRAGE <= t < _FIN_ASH + 40:
            self._draw_barrage(scr, t - _FIN_BARRAGE, bx, by)
        # 5) CENDRES : la silhouette du dieu s'effrite et s'efface.
        if t >= _FIN_ASH:
            da = t - _FIN_ASH
            sheet = getattr(self, "_aegis_sheet_dark", None) or getattr(self, "_aegis_sheet", None)
            if sheet and da < 120:
                try:
                    frame = sheet.subsurface((0, 0, self._aegis_frame_w, sheet.get_height()))
                    scaled = pygame.transform.scale(frame, (b.vis * 2, b.vis * 2)).copy()
                    scaled.set_alpha(max(0, 200 - da * 2))
                    scr.blit(scaled, (bx - b.vis, by - b.vis))
                except Exception:
                    pass

        # ═════════ CAMÉRA ═════════
        self._apply_finale_cam(scr, t, bx, by, px, py)

        # ═════════ SURCOUCHES (non zoomées) ═════════
        BAR = 70
        if t < 30:                  bh = int(BAR * t / 30)
        elif t > _FIN_ASH_END - 40: bh = int(BAR * max(0, _FIN_ASH_END - t) / 40)
        else:                       bh = BAR
        if bh > 0:
            for yb in (0, H - bh):
                bar = pygame.Surface((W, bh), pygame.SRCALPHA); bar.fill((4, 1, 8, 236))
                ly = bh - 1 if yb == 0 else 0
                pygame.draw.line(bar, (150, 24, 100), (0, ly), (W, ly), 2)
                scr.blit(bar, (0, yb))
        # Répliques.
        if _FIN_SURPRISE <= t < _FIN_REVEAL:
            self._fin_textbox((255, 120, 130), "Le temps... le temps s'est ARRÊTÉ ?!", speaker="AEGIS")
        elif _FIN_QUESTION <= t < _FIN_ANSWER:
            self._fin_textbox((255, 90, 90), "QUI... QUI ES-TU ?!", speaker="AEGIS")
        elif _FIN_ANSWER <= t < _FIN_BARRAGE:
            a = min(255, int((t - _FIN_ANSWER) * 8))
            if t > _FIN_BARRAGE - 50: a = max(0, 255 - int((t - (_FIN_BARRAGE - 50)) * 5))
            if a > 0:
                s = self.font_big.render("Je suis la fin.", True, (236, 240, 248))
                sh = self.font_big.render("Je suis la fin.", True, (10, 12, 20))
                s.set_alpha(a); sh.set_alpha(a)
                r = s.get_rect(center=(W // 2, H // 2 - 40))
                scr.blit(sh, (r.x + 3, r.y + 3)); scr.blit(s, r)
        elif _FIN_BARRAGE <= t < _FIN_ASH:
            tb = t - _FIN_BARRAGE
            for (l0, l1, txt) in ((0, 150, "Attends— ATTENDS !"),
                                  (150, 310, "Pitié... je t'en supplie, ARRÊTE !"),
                                  (310, 470, "Je peux tout changer ! ÉPARGNE-MOI !"),
                                  (470, 640, "COMMENT OSES-TU ?! JE SUIS UN DIEU !!"),
                                  (640, 790, "Tu n'es qu'un... un MORTEL—"),
                                  (790, 890, "non... non non NON—"),
                                  (890, 980, "je ne veux pas dispar—")):
                if l0 <= tb < l1:
                    aa = 255
                    if tb < l0 + 14: aa = int(255 * (tb - l0) / 14)
                    elif tb > l1 - 16: aa = int(255 * (l1 - tb) / 16)
                    col = (255, 80, 80) if any(w in txt for w in ("OSE", "DIEU", "MORTEL")) else (255, 150, 200)
                    self._fin_textbox(col, txt, alpha=max(0, min(255, aa)), speaker="AEGIS")
                    break
        # CARTE « LA FIN » (name-drop façon Susano'o, au climax du déluge).
        if _FIN_BARRAGE + 470 <= t < _FIN_BARRAGE + 600:
            self._draw_namecard(scr, t - (_FIN_BARRAGE + 470))
        # « fin » (après les cendres).
        if t >= _FIN_ASH + 40:
            a = min(255, int((t - (_FIN_ASH + 40)) * 5))
            if t > _FIN_ASH_END - 40: a = max(0, 255 - int((t - (_FIN_ASH_END - 40)) * 5))
            if a > 0:
                rev = self.font_big.render("fin", True, (238, 238, 245))
                rsh = self.font_big.render("fin", True, (20, 6, 24))
                rev.set_alpha(a); rsh.set_alpha(a)
                rr = rev.get_rect(center=(W // 2, H // 2 - 150))
                scr.blit(rsh, (rr.x + 3, rr.y + 3)); scr.blit(rev, rr)

    def _draw_finale_ending(self):
        scr = self.screen; W, H = WIDTH, HEIGHT; t = self.boss.finale_t
        cam = self.cam; bx = int(self.boss.x - cam[0]); by = int(self.boss.y - cam[1])
        # (Aegis n'est plus : il a été réduit en CENDRES. Les motes résiduelles
        #  sont émises en update et dérivent doucement vers le haut.)
        # Vignette qui se referme (le vide engloutit tout).
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vg, (0, 0, 0, min(170, 40 + t // 4)), (0, 0, W, H), 180)
        scr.blit(vg, (0, 0))
        # TEXTE FINAL — une ligne à la fois.
        lines = ["Les dieux se croyaient la fin de toute chose.",
                 "Ils n'avaient jamais rencontré ce qui vient APRÈS.",
                 "Plus de rêve. Plus de monde. Plus de dieu.",
                 "Seulement lui. Et le silence qu'il laisse."]
        y0 = H // 2 - 70
        for i, ln in enumerate(lines):
            ap = t - 120 - i * 130
            if ap <= 0: continue
            a = min(255, int(ap * 5))
            col = (235, 70, 70) if i == 3 else (220, 215, 235)
            s = self.font_med.render(ln, True, col); s.set_alpha(a)
            scr.blit(s, s.get_rect(center=(W // 2, y0 + i * 46)))
        if self.finale_done:
            pulse = 0.5 + 0.5 * math.sin(self.frame * 0.06)
            hint = self.font_sm.render("[ R ]  Fin", True, (int(150 + 80 * pulse),) * 3)
            scr.blit(hint, hint.get_rect(center=(W // 2, H - 50)))

    def add_shake(self, strength, frames=10):
        self.shake = max(self.shake, frames)
        self.shake_strength = max(self.shake_strength, strength)

    def start_slowmo(self, frames):
        self.slowmo = max(self.slowmo, frames)

    def flash(self, col=(255, 255, 255), frames=18):
        """Déclenche un flash plein écran qui s'estompe sur `frames` frames."""
        self.flash_col = col
        self.flash_t = frames
        self.flash_max = frames

    def set_subtitle(self, text, frames=150, voice=_VOICE_AEGIS_VOID):
        self.subtitle_text = text
        self.subtitle_t = frames
        self.subtitle_max = frames
        # Aegis « parle » : sa voix grave se déclenche aussi en combat (hors « ... »).
        if voice and text and text.strip() not in ("", "...", "…"):
            self._play_voice_line(voice)

    def announce_phase(self, text):
        self.announce_text = text
        self.announce_t = self.announce_max

    def set_attack_callout(self, text, frames=82):
        # Nom de l'attaque spéciale en cours : claque à l'écran puis s'efface.
        self.callout_text = text
        self.callout_t = frames
        self.callout_max = frames

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
                    if self.show_god_dialog:
                        if event.key == pygame.K_ESCAPE:
                            self.show_god_dialog = False
                            self.god_input = ""
                        elif event.key == pygame.K_BACKSPACE:
                            self.god_input = self.god_input[:-1]
                        elif event.key == pygame.K_RETURN:
                            if self.god_input == "1234":
                                self.god_mode = True
                            self.show_god_dialog = False
                            self.god_input = ""
                        else:
                            if len(self.god_input) < 4:
                                self.god_input += event.unicode
                        continue
                    if event.key == pygame.K_TAB:
                        self.settings_open = not self.settings_open
                    if event.key == pygame.K_ESCAPE:
                        if self.state == STATE_TITLE:
                            running = False
                        elif self.state in (STATE_MOON, STATE_HUB, STATE_OVERWORLD):
                            self.toggle_pause()          # ouvre / ferme le menu pause
                        else:
                            self.reset_to_title()
                    elif self.paused:
                        # Menu pause ouvert : la navigation a priorité sur tout le reste.
                        _opts = self._pause_options()
                        if event.key == pygame.K_UP:
                            self.pause_sel = (self.pause_sel - 1) % len(_opts)
                        elif event.key == pygame.K_DOWN:
                            self.pause_sel = (self.pause_sel + 1) % len(_opts)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self._pause_select()
                    elif event.key == pygame.K_g:
                        self.show_god_dialog = True
                        self.god_input = ""
                    elif event.key == pygame.K_F11 or event.key == pygame.K_f:
                        # F11 (Windows) ET F (universel, Mac n'intercepte pas)
                        self.toggle_fullscreen()
                    elif event.key == pygame.K_RETURN and self.state == STATE_TITLE:
                        self.start_cinematic()
                    elif event.key == pygame.K_c and self.state == STATE_TITLE:
                        self.show_controls_popup = not self.show_controls_popup
                    elif event.key == pygame.K_p and self.state == STATE_TITLE:
                        now = time.time()
                        self.p_press_times = [t for t in self.p_press_times if now - t <= 5.0]
                        self.p_press_times.append(now)
                        if len(self.p_press_times) >= 20:
                            self.aegis_unlocked = True
                            self.phase5_unlocked = True
                            self.p_press_times = []
                        elif len(self.p_press_times) >= 10:
                            self.phase5_unlocked = True
                    # ── Bouclier (touche 1) ───────────────────────────────────────
                    elif (event.key == pygame.K_1 and self.state == STATE_MOON
                          and not self._input_locked()
                          and not self._finale_survival()    # FINALE : plus de bouclier
                          and self.shield_unlocked
                          and self.ability_shield_cd == 0
                          and self.ability_shield_t == 0):
                        self.ability_shield_t  = self.SHIELD_DUR
                        self.ability_shield_cd = self.SHIELD_CD
                        burst(self.particles,
                              self.player.rect.centerx, self.player.rect.centery,
                              20, (100, 200, 255), 6.0, 30, 0.0, 4)
                    # ── PASSER une cinématique (spam Espace/Entrée) ───────────────
                    elif (event.key in (pygame.K_SPACE, pygame.K_RETURN)
                          and self.state == STATE_MOON and self._skippable()):
                        self._skip_press()
                    # ── Dialogue Aegis post-boss ──────────────────────────────────
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == STATE_MOON and self.aegis_dialog_active:
                        line = _AEGIS_BOSS_LINES[self.aegis_dialog_line]
                        total_chars = len(line.replace('\n', ''))
                        chars_shown = min(total_chars, self.aegis_dialog_char_t // 2)
                        if chars_shown < total_chars:
                            self.aegis_dialog_char_t = total_chars * 2
                        else:
                            self._aegis_dialog_next()
                    # ── Cinématique : ENTRÉE / ESPACE → dialogue suivant ──────────
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == STATE_CINEMATIC:
                        line = _CIN_LINES[self.cin_line]
                        total_chars = len(line.replace('\n', ''))
                        chars_shown = min(total_chars, self.cin_char_t // 2)
                        if chars_shown < total_chars:
                            self.cin_char_t = total_chars * 2  # affiche tout immédiatement
                        elif self.cin_line > 0:
                            self._cin_next()
                    # ── Overworld / Pause ──────────────────────────────────────────
                    elif (event.key == pygame.K_p
                          and self.state in (STATE_OVERWORLD, STATE_MOON, STATE_HUB)):
                        self.toggle_pause()
                    elif event.key == pygame.K_r and self.state in (STATE_GAMEOVER, STATE_VICTORY):
                        self.start_overworld()
                    elif (event.key == pygame.K_r and self.state == STATE_MOON
                          and self.fighting_aegis and self.finale_done):
                        self.fighting_aegis = False
                        self.reset_to_title()
                    elif event.key == pygame.K_r and self.state == STATE_MOON and self.final_blow_hub_t > 0:
                        self.start_hub()
                    elif event.key == pygame.K_SPACE and self.state in (STATE_HUB, STATE_MOON) and not self._input_locked():
                        self.player.press_jump(self.particles)
                    elif event.key in (pygame.K_a, pygame.K_LSHIFT, pygame.K_RSHIFT) and self.state in (STATE_HUB, STATE_MOON) and not self._input_locked():
                        if self.player.try_dash(self.particles) and self.state == STATE_MOON and self.boss:
                            self._check_parry()
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_SPACE and self.state in (STATE_HUB, STATE_MOON) and not self._input_locked():
                        self.player.release_jump()
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state == STATE_TITLE:
                    if self.settings_open:
                        self.handle_settings_mouse(event.pos[0], event.pos[1])
                    if self.show_controls_popup and event.button in (4, 5):
                        self.controls_scroll += -1 if event.button == 4 else 1
                    if event.button == 1:
                        if self.start_btn_rect.collidepoint(event.pos):
                            self.phase5_mode = False
                            self.start_cinematic()
                        elif self.phase5_unlocked and self.start_phase5_btn_rect.collidepoint(event.pos):
                            self.phase5_mode = True
                            self.start_hub()
                        elif self.aegis_unlocked and self.start_aegis_btn_rect.collidepoint(event.pos):
                            self.start_aegis_fight()
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state in (STATE_HUB, STATE_MOON):
                    if self.settings_open:
                        self.handle_settings_mouse(event.pos[0], event.pos[1])
                    if self.show_controls_popup and event.button in (4, 5):
                        self.controls_scroll += -1 if event.button == 4 else 1
                    if event.button == 1 and not self._input_locked():
                        if self._finale_survival():
                            # FINALE : plus d'arc. Le clic n'active QUE la compétence
                            # « ?! » une fois la jauge pleine → le temps s'arrête.
                            if self.finale_gauge >= 1.0:
                                self._finale_activate_skill()
                        else:
                            mx, my = event.pos
                            a = self.player.fire_bow(mx, my, self.cam)
                            if a: self.arrows.append(a)
                elif event.type == pygame.MOUSEMOTION:
                    if self.settings_open and pygame.mouse.get_pressed()[0]:
                        self.handle_settings_mouse(event.pos[0], event.pos[1])

            do_update = True
            if self.slowmo > 0:
                self.slowmo -= 1
                if self.frame % 2 != 0:
                    do_update = False

            if self.state == STATE_TITLE:
                self.title_pulse_t += 1
                self.draw_title()
            elif self.state == STATE_CINEMATIC:
                if do_update:
                    self.update_cinematic()
                self.draw_cinematic()
            elif self.state == STATE_OVERWORLD:
                if do_update:
                    self.update_overworld()
                self.draw_overworld()
            elif self.state == STATE_HUB:
                if do_update and not self.paused: self.update_hub()
                # Mise à jour de l'angle de visée depuis la souris
                if self.player:
                    _mx, _my = pygame.mouse.get_pos()
                    _scx = self.player.rect.centerx - self.cam[0]
                    _scy = self.player.rect.centery - self.cam[1]
                    self.player._aim_angle = math.atan2(_my - _scy, _mx - _scx)
                self.draw_world(in_arena=False)
                self.draw_hub_overlay()
                if self.paused:
                    self.draw_pause_menu()
            elif self.state == STATE_MOON:
                if do_update and not self.paused: self.update_moon()
                # Mise à jour de l'angle de visée depuis la souris
                if self.player:
                    _mx, _my = pygame.mouse.get_pos()
                    _scx = self.player.rect.centerx - self.cam[0]
                    _scy = self.player.rect.centery - self.cam[1]
                    self.player._aim_angle = math.atan2(_my - _scy, _mx - _scx)
                self.draw_world(in_arena=True)
                self.draw_screen_flash()
                # IMPORTANT : pendant la FINALE, le coup fatal remet boss.dead=True,
                # mais il ne FAUT PAS réafficher le texte de mort (sinon ça écrase la
                # coupe/le dérive/la vraie fin). La finale gère son propre rendu.
                if (self.fighting_aegis and self.boss and self.boss.dead
                        and not getattr(self.boss, "finale_active", False)):
                    self.draw_aegis_ending()
                elif self.aegis_dialog_active:
                    self.draw_aegis_dialog()
                elif self.final_blow_hub_t > 0:
                    self._draw_victory_overlay()
                elif self._boss_cine_kind() is not None:
                    pass   # NÉMÉSIS / COURROUX : aucun HUD (cinématique plein écran)
                elif isinstance(self.boss, AegisBoss) and getattr(self.boss, "finale_active", False):
                    pass   # FINALE : aucun HUD normal (la jauge « ?! » est dessinée à part)
                elif (self.boss and isinstance(self.boss, AegisBoss)
                      and self.boss.state == "intro"):
                    self.draw_announce()      # ENTRÉE : seulement le nom de phase
                    self.draw_subtitle()      # + les répliques du dieu
                else:
                    self.draw_boss_ui()
                    self.draw_announce()
                    self.draw_subtitle()
                    self.draw_attack_callout()
                    self.draw_shield_ability()
                    self.draw_skill_bar()
                # Indice « passer » (s'auto-affiche seulement pendant une cinématique).
                self._draw_skip_hint()
                if self.paused:
                    self.draw_pause_menu()
            elif self.state == STATE_GAMEOVER:
                self.draw_world(in_arena=(self.boss is not None))
                self.draw_gameover()
            elif self.state == STATE_VICTORY:
                # Legacy fallback : si on arrive ici, retour hub immédiat
                self.start_hub()
                continue

            if self.show_god_dialog:
                self.draw_god_dialog()

            if self.settings_open:
                self.draw_settings_overlay()

            pygame.display.flip()

        pygame.quit()

    # ── Cinématique ──────────────────────────────────────────────────────────

    def start_cinematic(self):
        self.cin_line   = 0
        self.cin_char_t = 0
        self.cin_hold_t = 0
        self.cin_fade   = 0
        self.state = STATE_CINEMATIC

    def _cin_next(self):
        self.cin_line   += 1
        self.cin_char_t  = 0
        self.cin_hold_t  = 0
        if self.cin_line >= len(_CIN_LINES):
            self.start_overworld()

    def update_cinematic(self):
        _prev = self.cin_char_t
        self.cin_char_t += 1
        if self.cin_line > 0:    # ligne 0 = « ... » du héros (groggy) = muet
            self._typewriter_blip(_CIN_LINES[self.cin_line], _prev,
                                  self.cin_char_t, _VOICE_AEGIS)
        self.cin_fade = min(60, self.cin_fade + 1)
        line = _CIN_LINES[self.cin_line]
        total_chars = len(line.replace('\n', ''))
        chars_shown = min(total_chars, self.cin_char_t // 2)
        # Première ligne ("...") s'avance automatiquement après 120 frames de pause
        if self.cin_line == 0 and chars_shown >= total_chars:
            self.cin_hold_t += 1
            if self.cin_hold_t > 120:
                self._cin_next()

    def draw_cinematic(self):
        surf = self.screen
        t    = self.frame
        surf.fill((8, 5, 18))

        # Étoiles de fond
        for i in range(80):
            rx = (i * 137 + 42) % WIDTH
            ry = (i * 91  + 17) % (HEIGHT - 180)
            pygame.draw.circle(surf, (180, 160, 240), (rx, ry), 1)

        # ── Aegis angélique (centre-haut) ─────────────────────────────────
        ax, ay = WIDTH // 2, HEIGHT // 2 - 60
        # Halo
        for r in range(90, 15, -12):
            a = max(0, 55 - r // 2)
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            glow.fill((100, 150, 255, a))
            surf.blit(glow, (ax - r, ay - r))
        pygame.draw.circle(surf, (50, 90, 190), (ax, ay), 44)
        pygame.draw.circle(surf, (90, 150, 255), (ax, ay), 34)
        pygame.draw.circle(surf, (200, 220, 255), (ax, ay), 19)
        pygame.draw.circle(surf, (255, 245, 210), (ax, ay), 10)
        # Couronne de rayons
        for i in range(7):
            angle = -math.pi / 2 + i * (math.pi * 2 / 7)
            ex = ax + int(math.cos(angle) * 55)
            ey = ay + int(math.sin(angle) * 55)
            pygame.draw.line(surf, (160, 200, 255), (ax, ay), (ex, ey), 2)
            pygame.draw.circle(surf, (220, 240, 255), (ex, ey), 4)
        # Anneau pulsant
        pulse = int(abs(math.sin(t * 0.04)) * 14)
        cr = 62 + pulse
        ring = pygame.Surface((cr * 2, cr * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (140, 190, 255, 45), (cr, cr), cr, 3)
        surf.blit(ring, (ax - cr, ay - cr))

        # ── Dialogue box ──────────────────────────────────────────────────
        line = _CIN_LINES[self.cin_line]
        total_chars = len(line.replace('\n', ''))
        chars_shown = min(total_chars, self.cin_char_t // 2)

        box_h  = 150
        box_y  = HEIGHT - box_h - 28
        box_x  = 40
        box_w  = WIDTH - 80
        box    = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((14, 8, 32, 215))
        surf.blit(box, (box_x, box_y))
        pygame.draw.rect(surf, (80, 120, 210), (box_x, box_y, box_w, box_h), 2, border_radius=6)

        # Nom
        name_surf = self.font_sm.render("AEGIS", True, (140, 200, 255))
        surf.blit(name_surf, (box_x + 18, box_y + 12))

        # Texte lettre à lettre
        shown_count = 0
        y_off = box_y + 42
        for dl in line.split('\n'):
            if shown_count >= chars_shown:
                break
            shown_here = dl[:max(0, chars_shown - shown_count)]
            shown_count += len(dl)
            ts = self.font_med.render(shown_here, True, (215, 210, 255))
            surf.blit(ts, (box_x + 18, y_off))
            y_off += 38

        # Indicateur "ENTRÉE" clignote quand texte complet
        if chars_shown >= total_chars and self.cin_line > 0:
            if (t // 25) % 2 == 0:
                hint = self.font_sm.render("[ ENTRÉE ]", True, (150, 175, 255))
                surf.blit(hint, (WIDTH - 170, HEIGHT - 45))

        # Fade-in overlay
        if self.cin_fade < 60:
            alpha = max(0, min(255, 255 - int(self.cin_fade * 4.25)))
            fo = pygame.Surface((WIDTH, HEIGHT))
            fo.fill((0, 0, 0))
            fo.set_alpha(alpha)
            surf.blit(fo, (0, 0))

    # ── Overworld ────────────────────────────────────────────────────────────

    def start_overworld(self):
        self.fighting_aegis = False
        T = OW_TILE
        self.ow_walls   = []
        self.ow_portals = []
        for row_i, row in enumerate(_OW_TILES):
            for col_i, tile in enumerate(row):
                r = pygame.Rect(col_i * T, row_i * T, T, T)
                if tile == OW_WALL:
                    self.ow_walls.append(r)
                elif tile == OW_PORTAL_M:
                    self.ow_portals.append(r)
        sx = _OW_SPAWN_COL * T + T // 2
        sy = _OW_SPAWN_ROW * T + T // 2
        self.ow_player  = OverworldPlayer(sx, sy)
        self.ow_cam     = [0, 0]
        self.paused     = False
        self.state      = STATE_OVERWORLD

    def update_overworld(self):
        if self.paused:
            return
        keys = pygame.key.get_pressed()
        self.ow_player.update(keys, self.ow_walls)
        # Caméra centrée sur le joueur, clampée aux bords de la map
        T     = OW_TILE
        map_w = len(_OW_TILES[0]) * T
        map_h = len(_OW_TILES)    * T
        px    = int(self.ow_player.x) - WIDTH  // 2
        py    = int(self.ow_player.y) - HEIGHT // 2
        self.ow_cam[0] = max(0, min(px, map_w - WIDTH))
        self.ow_cam[1] = max(0, min(py, map_h - HEIGHT))
        # Collision portail → combat
        pr = self.ow_player._rect()
        for p in self.ow_portals:
            if pr.colliderect(p):
                self.start_moon()
                return

    def draw_overworld(self):
        surf = self.screen
        cam  = self.ow_cam
        T    = OW_TILE
        t    = self.frame

        surf.fill((8, 5, 18))

        # Tuiles visibles
        col0 = max(0, cam[0] // T)
        col1 = min(len(_OW_TILES[0]), (cam[0] + WIDTH)  // T + 2)
        row0 = max(0, cam[1] // T)
        row1 = min(len(_OW_TILES),    (cam[1] + HEIGHT) // T + 2)

        for ri in range(row0, row1):
            for ci in range(col0, col1):
                tile = _OW_TILES[ri][ci]
                rx   = ci * T - cam[0]
                ry   = ri * T - cam[1]
                if tile == OW_WALL:
                    pygame.draw.rect(surf, (20, 13, 35), (rx, ry, T, T))
                    pygame.draw.rect(surf, (38, 24, 58), (rx, ry, T, T), 1)
                elif tile == OW_FLOOR:
                    pygame.draw.rect(surf, (28, 20, 42), (rx, ry, T, T))
                    pygame.draw.rect(surf, (36, 27, 52), (rx, ry, T, T), 1)
                elif tile == OW_PORTAL_M:
                    pulse = int(abs(math.sin(t * 0.05 + ci + ri)) * 28)
                    pygame.draw.rect(surf, (55 + pulse, 18, 78 + pulse), (rx, ry, T, T))
                    pygame.draw.rect(surf, (140, 80, 200), (rx, ry, T, T), 2)

        # Label portail Lune
        if self.ow_portals:
            p   = self.ow_portals[0]
            lx  = p.x + p.w // 2 - cam[0]
            ly  = p.y - 24 - cam[1]
            lbl = self.font_sm.render("Temple de la Lune", True, (190, 130, 255))
            surf.blit(lbl, (lx - lbl.get_width() // 2, ly))

        self.ow_player.draw(surf, cam, t)

        # HUD minimal
        hint = self.font_sm.render("P — Pause", True, (80, 70, 110))
        surf.blit(hint, (10, 10))

        if self.paused:
            self.draw_pause_menu()

        if self.save_anim_t > 0:
            self.draw_save_animation()
            self.save_anim_t += 1
            if self.save_anim_t > self.SAVE_ANIM_DUR:
                self.save_anim_t = 0

    # ── Menu Pause ───────────────────────────────────────────────────────────

    def toggle_pause(self):
        self.paused = not self.paused
        try:
            if self.paused:
                pygame.mixer.music.pause(); pygame.mixer.pause()   # fige musique + SFX
            else:
                pygame.mixer.music.unpause(); pygame.mixer.unpause()
        except Exception:
            pass
        if self.paused:
            self.pause_sel = 0

    def _pause_options(self):
        # En combat / hub : pas de sauvegarde (la save est liée à l'overworld).
        if self.state == STATE_OVERWORLD:
            return ["Reprendre", "Sauvegarder", "Quitter"]
        return ["Reprendre", "Quitter au menu"]

    def _pause_select(self):
        opts = self._pause_options()
        if not (0 <= self.pause_sel < len(opts)):
            self.pause_sel = 0
        label = opts[self.pause_sel]
        if label == "Reprendre":
            self.toggle_pause()
        elif label == "Sauvegarder":
            self.save_game()          # ferme déjà le menu pause
        else:                          # « Quitter » / « Quitter au menu »
            self.reset_to_title()      # coupe la musique + retour au titre

    def draw_pause_menu(self):
        surf = self.screen
        # Overlay
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        surf.blit(ov, (0, 0))
        # Panneau
        pw, ph = 340, 270
        pmx = (WIDTH - pw) // 2
        pmy = (HEIGHT - ph) // 2
        pn  = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pn.fill((18, 10, 36, 235))
        surf.blit(pn, (pmx, pmy))
        pygame.draw.rect(surf, (90, 60, 165), (pmx, pmy, pw, ph), 2, border_radius=8)
        # Titre
        ti = self.font_med.render("— PAUSE —", True, (200, 180, 255))
        surf.blit(ti, (pmx + (pw - ti.get_width()) // 2, pmy + 22))
        # Options
        opts = self._pause_options()
        for i, opt in enumerate(opts):
            sel = (i == self.pause_sel)
            col = (255, 230, 100) if sel else (175, 155, 225)
            tx, ty = pmx + 66, pmy + 85 + i * 54
            ts  = self.font_med.render(opt, True, col)
            surf.blit(ts, (tx, ty))
            if sel:   # curseur triangulaire (indépendant de la police)
                cy = ty + ts.get_height() // 2
                pygame.draw.polygon(surf, (255, 230, 100),
                                    [(tx - 24, cy - 9), (tx - 24, cy + 9), (tx - 9, cy)])

    def save_game(self):
        data = {
            "ow_x": self.ow_player.x if self.ow_player else 0,
            "ow_y": self.ow_player.y if self.ow_player else 0,
            "bosses_defeated": ["moon"] if self.shield_unlocked else [],
            "abilities": ["shield"] if self.shield_unlocked else [],
        }
        path = os.path.join(os.path.expanduser("~"), ".dreamspawn_save.json")
        try:
            with open(path, 'w') as f:
                json.dump(data, f)
            self.save_anim_t = 1      # déclenche l'animation DS
            if self.paused:
                self.toggle_pause()   # ferme le menu pause
        except Exception:
            pass

    # ── Dialogue Aegis post-boss ─────────────────────────────────────────────

    def start_aegis_dialog(self):
        self.aegis_dialog_active = True
        self.aegis_dialog_line   = 0
        self.aegis_dialog_char_t = 0
        self.aegis_dialog_fade   = 0
        self._aegis_anim_t       = 0

    def _aegis_dialog_next(self):
        self.aegis_dialog_line   += 1
        self.aegis_dialog_char_t  = 0
        if self.aegis_dialog_line >= len(_AEGIS_BOSS_LINES):
            self.aegis_dialog_active = False
            self.shield_unlocked     = True   # Aegis donne le bouclier
            self.start_overworld()

    def update_aegis_dialog(self):
        _prev = self.aegis_dialog_char_t
        self.aegis_dialog_char_t += 1
        self._typewriter_blip(_AEGIS_BOSS_LINES[self.aegis_dialog_line],
                              _prev, self.aegis_dialog_char_t, _VOICE_AEGIS)
        self.aegis_dialog_fade    = min(60, self.aegis_dialog_fade + 1)
        self._aegis_anim_t       += 1

    def draw_aegis_dialog(self):
        surf = self.screen
        t    = self._aegis_anim_t

        # Overlay semi-transparent sur le fond de combat
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        surf.blit(ov, (0, 0))

        # ── Sprite Aegis (centré, très grand) ────────────────────────────
        # Taille cible : hauteur 520px, ratio conservé (224/240 ≈ 0.933)
        DST_H = 520
        DST_W = int(DST_H * 224 / 240)   # ≈ 485px
        sprite_cx = WIDTH // 2
        sprite_y  = HEIGHT // 2 - DST_H // 2 - 30   # légèrement au-dessus du centre
        if self._aegis_sheet:
            fw   = self._aegis_frame_w          # 240
            n_fr = self._aegis_sheet.get_width() // fw   # 15
            frame  = (t // 7) % n_fr
            region = pygame.Rect(frame * fw, 0, fw, self._aegis_sheet.get_height())
            raw    = self._aegis_sheet.subsurface(region)
            scaled = pygame.transform.scale(raw, (DST_W, DST_H))
            # Halo lumineux derrière
            for r in (160, 130, 100, 70):
                a  = max(0, 55 - r // 4)
                gs = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                gs.fill((120, 170, 255, a))
                surf.blit(gs, (sprite_cx - r, sprite_y + DST_H // 2 - r))
            surf.blit(scaled, (sprite_cx - DST_W // 2, sprite_y))
        else:
            ax, ay = sprite_cx, sprite_y + DST_H // 2
            for r in (160, 120, 80, 40):
                a  = max(0, 55 - r // 4)
                gs = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                gs.fill((120, 170, 255, a))
                surf.blit(gs, (ax - r, ay - r))
            pygame.draw.circle(surf, (60, 110, 200), (ax, ay), 80)
            pygame.draw.circle(surf, (200, 225, 255), (ax, ay), 35)

        # ── Boîte de dialogue (bas gauche) ───────────────────────────────
        line        = _AEGIS_BOSS_LINES[self.aegis_dialog_line]
        total_chars = len(line.replace('\n', ''))
        chars_shown = min(total_chars, self.aegis_dialog_char_t // 2)

        box_w, box_h = WIDTH - 80, 150
        box_x, box_y = 40, HEIGHT - box_h - 28
        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill((14, 8, 32, 220))
        surf.blit(box, (box_x, box_y))
        pygame.draw.rect(surf, (80, 130, 220), (box_x, box_y, box_w, box_h), 2, border_radius=6)

        name_s = self.font_sm.render("AEGIS", True, (140, 205, 255))
        surf.blit(name_s, (box_x + 18, box_y + 12))

        shown_count = 0
        y_off = box_y + 42
        for dl in line.split('\n'):
            if shown_count >= chars_shown:
                break
            shown_here  = dl[:max(0, chars_shown - shown_count)]
            shown_count += len(dl)
            ts = self.font_med.render(shown_here, True, (215, 210, 255))
            surf.blit(ts, (box_x + 18, y_off))
            y_off += 38

        # Indicateur ENTRÉE
        if chars_shown >= total_chars:
            if (t // 25) % 2 == 0:
                hint = self.font_sm.render("[ ENTRÉE ]", True, (150, 180, 255))
                surf.blit(hint, (WIDTH - 175, HEIGHT - 45))

        # Fade-in
        if self.aegis_dialog_fade < 60:
            alpha = max(0, min(255, 255 - int(self.aegis_dialog_fade * 4.25)))
            fo = pygame.Surface((WIDTH, HEIGHT))
            fo.fill((0, 0, 0))
            fo.set_alpha(alpha)
            surf.blit(fo, (0, 0))

    # ── Cinématique d'ENTRÉE d'Aegis (15 s) ─────────────────────────────────
    def _draw_aegis_intro(self):
        """Entrée d'Aegis : descente, éveil, révélation (façon Sans/Asgore)."""
        boss = self.boss; scr = self.screen
        t = boss.intro_t; T = 900
        W, H = WIDTH, HEIGHT; cam = self.cam
        bx = int(boss.x - cam[0]); by = int(boss.y - cam[1])

        def ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)

        # 1) FX monde : ONDE DE CHOC dorée propre, émise du sol à l'éveil.
        if 430 <= t < 580:
            d = t - 430
            yg = by + int(boss.vis * 0.92)
            for k in range(2):
                dd = d - k * 14
                if dd <= 0: continue
                rr = int(dd * 7); aa = max(0, int(170 - dd * 1.8))
                if aa <= 0 or rr <= 0: continue
                sw = pygame.Surface((rr * 2 + 8, rr * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(sw, (255, 205, 120, aa), (rr + 4, rr + 4), rr, 4)
                scr.blit(sw, (bx - rr - 4, yg - rr - 4), special_flags=pygame.BLEND_RGBA_ADD)

        # 2) ZOOM : suit la descente puis RECULE pour révéler l'échelle du dieu.
        kf = [
            (0,   bx, max(70, by), 2.30),
            (150, bx, max(70, by), 2.30),
            (430, bx, by,          1.95),
            (620, bx, by,          1.45),
            (820, bx, by,          1.45),
            (T,   bx, by,          1.00),
        ]
        fx, fy, zoom = bx, by, 1.0
        for i in range(len(kf) - 1):
            t0, fx0, fy0, z0 = kf[i]; t1, fx1, fy1, z1 = kf[i + 1]
            if t0 <= t <= t1:
                e = ease((t - t0) / float(max(1, t1 - t0)))
                fx = fx0 + (fx1 - fx0) * e; fy = fy0 + (fy1 - fy0) * e
                zoom = z0 + (z1 - z0) * e; break
        if 430 <= t < 446:                              # coup de zoom sec à l'éveil
            zoom *= 1.0 + 0.10 * (1 - (t - 430) / 16.0)
        if zoom > 1.01:
            sw = max(2, int(W / zoom)); sh = max(2, int(H / zoom))
            sx = max(0, min(W - sw, int(fx) - sw // 2))
            sy = max(0, min(H - sh, int(fy) - sh // 2))
            sub = scr.subsurface(pygame.Rect(sx, sy, sw, sh))
            scr.blit(pygame.transform.scale(sub.copy(), (W, H)), (0, 0))

        # 3) Surcouches plein écran (letterbox, vignette, carte-titre, fondu).
        bar_max = 78
        if t < 40: bar_h = int(bar_max * t / 40)
        elif t > T - 50: bar_h = int(bar_max * max(0, T - t) / 50)
        else: bar_h = bar_max
        if bar_h > 0:
            for yb in (0, H - bar_h):
                bar = pygame.Surface((W, bar_h), pygame.SRCALPHA); bar.fill((4, 0, 8, 240))
                ly = bar_h - 1 if yb == 0 else 0
                pygame.draw.line(bar, (180, 20, 120), (0, ly), (W, ly), 2)
                scr.blit(bar, (0, yb))
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vg, (90, 0, 60, 90), (0, 0, W, H), 130)
        scr.blit(vg, (0, 0))
        if 430 <= t < 600:                              # carte-titre « AEGIS »
            a = min(255, int((t - 430) * 12))
            if t > 560: a = max(0, 255 - int((t - 560) * 6))
            if a > 0:
                scale = 1.0 + 0.5 * ease(min(1.0, (t - 430) / 60.0))
                base = self.font_big.render("AEGIS", True, (255, 60, 60))
                bw = max(1, int(base.get_width() * scale)); bh = max(1, int(base.get_height() * scale))
                big = pygame.transform.smoothscale(base, (bw, bh))
                shs = pygame.transform.smoothscale(self.font_big.render("AEGIS", True, (30, 0, 0)), (bw, bh))
                big.set_alpha(a); shs.set_alpha(a)
                rr = big.get_rect(center=(W // 2, H // 2 - 36))
                scr.blit(shs, (rr.x + 4, rr.y + 4)); scr.blit(big, rr)

        # Répliques du dieu — LISIBLES (caisson sombre + ombre) dans le bas.
        def _gline(txt, t0, t1):
            if not (t0 <= t < t1): return
            a = 255
            if t < t0 + 22: a = int(255 * (t - t0) / 22)
            elif t > t1 - 25: a = int(255 * (t1 - t) / 25)
            a = max(0, min(255, a))
            if a <= 0: return
            self._cine_voice_once(("intro", txt), _VOICE_AEGIS_VOID)   # voix grave d'Aegis
            s = self.font_med.render(txt, True, (255, 238, 214))
            sh = self.font_med.render(txt, True, (16, 2, 24))
            box = pygame.Surface((s.get_width() + 54, s.get_height() + 20), pygame.SRCALPHA)
            box.fill((6, 1, 12, int(180 * a / 255)))
            br = box.get_rect(center=(W // 2, H - 40)); scr.blit(box, br)
            s.set_alpha(a); sh.set_alpha(a)
            r = s.get_rect(center=(W // 2, H - 40))
            scr.blit(sh, (r.x + 2, r.y + 2)); scr.blit(s, r)
        _gline("Petite chose… tu oses gravir jusqu'à MOI ?", 600, 770)
        _gline("Soit. Que ton jugement commence.", 770, 900)

        if t < 70:                                      # fondu d'entrée (depuis le noir)
            fo = pygame.Surface((W, H)); fo.fill((0, 0, 0)); fo.set_alpha(int(255 * (1 - t / 70.0)))
            scr.blit(fo, (0, 0))

    # ── Cinématique de fin : mort d'Aegis ───────────────────────────────────

    def draw_aegis_ending(self):
        surf = self.screen
        t = self.aegis_ending_t
        W, H = WIDTH, HEIGHT
        cam = self.cam
        boss = self.boss
        bx = int(boss.x - cam[0]); by = int(boss.y - cam[1])

        def ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)

        # ════════ CINÉMATIQUE DE MORT (10 s = 600 frames) ════════
        if t < 600:
            # 1) Fissures + faisceaux de lumière jaillissant du dieu agonisant.
            if t < 470:
                erupt = ease(min(1.0, t / 430.0))
                fxs = pygame.Surface((W, H), pygame.SRCALPHA)
                nb = int(6 + 14 * erupt)
                for i in range(nb):
                    a = i * math.tau / nb + t * 0.03
                    L = (90 + 250 * erupt) * (0.7 + 0.3 * math.sin(t * 0.2 + i))
                    col = (255, 255, 255) if i % 3 == 0 else (235, 40, 165)
                    pygame.draw.line(fxs, (*col, max(0, int(150 * erupt))),
                                     (bx, by), (int(bx + math.cos(a) * L), int(by + math.sin(a) * L)),
                                     max(2, int(2 + 5 * erupt)))
                cr = int(20 + 72 * erupt)
                pygame.draw.circle(fxs, (255, 240, 250, max(0, int(180 * erupt))), (bx, by), cr)
                pygame.draw.circle(fxs, (255, 255, 255, max(0, int(220 * erupt))), (bx, by), max(4, cr // 2))
                surf.blit(fxs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            # 2) Zoom doux sur le dieu mourant, puis recul.
            if t < 320:   zoom = 1.0 + 0.4 * ease(t / 320.0)
            elif t < 430: zoom = 1.4
            else:         zoom = 1.4 - 0.4 * ease((t - 430) / 130.0)
            if zoom > 1.01 and t < 560:
                sw = max(2, int(W / zoom)); sh = max(2, int(H / zoom))
                sx = max(0, min(W - sw, bx - sw // 2)); sy = max(0, min(H - sh, by - sh // 2))
                sub = surf.subsurface(pygame.Rect(sx, sy, sw, sh))
                surf.blit(pygame.transform.scale(sub.copy(), (W, H)), (0, 0))

            # 3) Ondes de choc de l'éclatement.
            if 440 <= t < 540:
                for k in range(3):
                    d = (t - 440) - k * 10
                    if d <= 0: continue
                    rr = int(d * 11); aa = max(0, int(220 - d * 3))
                    if aa <= 0 or rr <= 0: continue
                    sw2 = pygame.Surface((rr * 2 + 10, rr * 2 + 10), pygame.SRCALPHA)
                    pygame.draw.circle(sw2, (255, 230, 250, aa), (rr + 5, rr + 5), rr, max(2, 9 - k * 2))
                    surf.blit(sw2, (W // 2 - rr - 5, H // 2 - rr - 5), special_flags=pygame.BLEND_RGBA_ADD)

            # 4) White-out de l'éclatement.
            if 440 <= t < 500:
                fa = max(0, int(255 * (1 - (t - 440) / 60.0)))
                fs = pygame.Surface((W, H)); fs.fill((255, 255, 255)); fs.set_alpha(fa)
                surf.blit(fs, (0, 0))

            # 5) Assombrissement progressif vers le noir (500 → 600).
            if t > 500:
                fa = int(255 * min(1.0, (t - 500) / 100.0))
                fo = pygame.Surface((W, H)); fo.fill((0, 0, 0)); fo.set_alpha(fa)
                surf.blit(fo, (0, 0))
            return

        # ════════ ÉCRAN DE FIN : texte de mort (t ≥ 600) ════════
        veil = pygame.Surface((W, H)); veil.fill((0, 0, 0)); surf.blit(veil, (0, 0))
        line_t = t - 600
        per_line = 70
        cx = W // 2
        y0 = H // 2 - (len(_AEGIS_DEATH_LINES) * 22)
        for i, line in enumerate(_AEGIS_DEATH_LINES):
            appear = line_t - i * per_line
            if appear <= 0:
                continue
            if appear == 1:    # 1re frame visible → blip grave (Aegis mourant)
                self._play_text_blip(_VOICE_AEGIS_VOID)
            alpha = min(255, int(appear * 6))
            col = (200, 160, 255) if i < 2 else (220, 220, 235)
            s = self.font_med.render(line, True, col)
            s.set_alpha(alpha)
            surf.blit(s, s.get_rect(center=(cx, y0 + i * 44)))

        # PAS de prompt [R] ici : c'est un FAUX ending. Le joueur croit que c'est
        # fini… puis la fissure s'ouvre (la vraie fin prend le relais à te=1150).

    # ── Animation sauvegarde style DS ───────────────────────────────────────

    def draw_save_animation(self):
        surf = self.screen
        t    = self.save_anim_t
        DUR  = self.SAVE_ANIM_DUR

        # Fade in/out de l'overlay
        if t < 20:
            alpha = int(210 * t / 20)
        elif t > DUR - 25:
            alpha = int(210 * (DUR - t) / 25)
        else:
            alpha = 210
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 12, alpha))
        surf.blit(ov, (0, 0))
        if t < 12:
            return

        ta = min(255, int(255 * (t - 12) / 18))
        cx, cy = WIDTH // 2, HEIGHT // 2 - 30

        # Étoiles tournantes (style DS)
        for i in range(8):
            angle = math.radians(t * 4 + i * 45)
            r_orb = 38 + int(8 * math.sin(math.radians(t * 7 + i * 55)))
            ox = cx + int(math.cos(angle) * r_orb)
            oy = cy + int(math.sin(angle) * r_orb)
            sz = 3 + int(2 * math.sin(math.radians(t * 9 + i * 40)))
            gs = pygame.Surface((sz * 2 + 2, sz * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 225, 110, ta), (sz + 1, sz + 1), sz)
            surf.blit(gs, (ox - sz - 1, oy - sz - 1))

        # Halo central
        for r in (32, 22, 13):
            hg = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            hg.fill((130, 190, 255, max(0, ta * 60 // 255)))
            surf.blit(hg, (cx - r, cy - r))
        pygame.draw.circle(surf, (210, 235, 255), (cx, cy), 10)

        # Texte "SAUVEGARDE..."
        dots = "." * ((t // 18) % 4)
        ts = self.font_med.render(f"SAUVEGARDE{dots}", True, (220, 215, 255))
        ts.set_alpha(ta)
        surf.blit(ts, ts.get_rect(center=(cx, HEIGHT // 2 + 22)))

        # Hint style DS
        if t > 45:
            ha = min(ta, 155)
            ht = self.font_sm.render("Ne pas éteindre la console.", True, (170, 165, 215))
            ht.set_alpha(ha)
            surf.blit(ht, ht.get_rect(center=(cx, HEIGHT // 2 + 66)))

    # ── Bouclier — dessin en combat ──────────────────────────────────────────

    def draw_shield_ability(self):
        """Anneau de bouclier autour du joueur quand ability_shield_t > 0."""
        if not self.player or self.ability_shield_t <= 0:
            return
        px = self.player.rect.centerx - self.cam[0]
        py = self.player.rect.centery - self.cam[1]
        frac = self.ability_shield_t / self.SHIELD_DUR
        pulse = int(abs(math.sin(self.frame * 0.15)) * 6)
        r = 36 + pulse
        alpha = int(180 * frac)
        ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (100, 200, 255, alpha), (r, r), r, 4)
        pygame.draw.circle(ring, (200, 240, 255, alpha // 2), (r, r), r - 6, 2)
        self.screen.blit(ring, (px - r, py - r))

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
            self.dream_exit_flash = 12   # frames de flash blanc

    def update_moon(self):
        if self.p5_cinematic_t > 0:
            self.p5_cinematic_t -= 1
        if self._skip_charge > 0:                 # la charge de skip retombe seule
            self._skip_charge = max(0.0, self._skip_charge - 2.5)
        self._tick_voice_queue()                  # voix d'Aegis (combat + cinématiques)
        keys = pygame.key.get_pressed()
        # ── FINALE — actes CINÉMATIQUES (prélude/dialogue/time-stop/fin) : gelés.
        #    L'acte « survival » N'est PAS géré ici : il continue en gameplay normal.
        if self._finale_cine():
            self._update_finale_cine()
            return
        # ── NÉMÉSIS : cinématique d'ouverture phase 7 — GAMEPLAY GELÉ ────────
        # On ne fait avancer que le boss (qui scripte la cinématique) et les
        # particules. Pas d'input, pas de physique joueur, pas de collisions,
        # pas de caméra (figée au départ) : le héros est intouchable.
        if self._boss_cine_kind() is not None:
            self.boss.update(self.player, self.beams, self.projectiles_boss,
                             self.rings, self.telegraphs, self.particles)
            self.player.invuln = max(self.player.invuln, 8)
            for part in self.particles: part.update()
            self.particles[:] = [p for p in self.particles if p.alive()]
            if self.announce_t > 0: self.announce_t -= 1
            if self.flash_t > 0: self.flash_t -= 1
            if self.subtitle_t > 0: self.subtitle_t -= 1
            if self.callout_t > 0: self.callout_t -= 1
            self.starfield.update(); self.dust.update()
            return
        # ── ENTRÉE grandiose d'Aegis (15 s) : gameplay gelé, héros planté. ──
        if (self.boss and isinstance(self.boss, AegisBoss)
                and self.boss.state == "intro"):
            self.boss.update(self.player, self.beams, self.projectiles_boss,
                             self.rings, self.telegraphs, self.particles)
            self.player.update(_FROZEN_KEYS, self.platforms, self.particles)
            self.cam = [0, 0]
            for part in self.particles: part.update()
            self.particles[:] = [p for p in self.particles if p.alive()]
            if self.announce_t > 0: self.announce_t -= 1
            if self.flash_t > 0: self.flash_t -= 1
            if self.subtitle_t > 0: self.subtitle_t -= 1
            if self.callout_t > 0: self.callout_t -= 1
            self.starfield.update(); self.dust.update()
            return
        pull_x, pull_y, pull_force = (None, None, 0.0)
        if self.boss:
            pull_x, pull_y, pull_force = self.boss.get_pull()
        self.player.update(keys, self.platforms, self.particles,
                           pull_x=pull_x, pull_y=pull_y, pull_force=pull_force)
        if self.god_mode:
            self.player.hp = self.player.max_hp
            # SPAM d'attaques : auto-tir rapide tant que le clic gauche est tenu.
            if not self._input_locked() and pygame.mouse.get_pressed()[0]:
                if self.player.bow_cd <= 0:
                    _mx, _my = pygame.mouse.get_pos()
                    _a = self.player.fire_bow(_mx, _my, self.cam)
                    if _a: self.arrows.append(_a)
                    self.player.bow_cd = 4     # cadence de spam (≈15 tirs/s)
        # ── Bouclier compétence ────────────────────────────────────────────
        if self.ability_shield_t > 0:
            self.ability_shield_t -= 1
            self.player.invuln = max(self.player.invuln, self.ability_shield_t)
        if self.ability_shield_cd > 0:
            self.ability_shield_cd -= 1
        # Invulnérabilité pendant les animations boss
        if self.boss and (self.boss.pre_dr_active or self.boss.final_blow_active):
            self.player.invuln = max(self.player.invuln, 10)
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
            if b.once and b._hit_done: continue
            if (b.hits_any_dim or b.dim == self.player.dimension) and b.rect.colliderect(self.player.rect):
                if self.player.hurt(b.dmg):
                    if b.once: b._hit_done = True
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
                            arrow_dmg = max(1, a.dmg // 2) if (self.boss and self.boss.post_dr) else a.dmg
                            if self.god_mode: arrow_dmg *= 4
                            dmg_done = self.boss.take_dmg(arrow_dmg, self.player.dimension, self.particles)
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

        # Orbes de soin — update + collecte
        for orb in self.heal_orbs:
            orb.update()
            if not orb.collected and orb.collect_rect().colliderect(self.player.rect):
                orb.collected = True
                self.player.heal(orb.amount)
                if self.boss:
                    self.boss._p4_orb_collected = True
                burst(self.particles, self.player.rect.centerx, self.player.rect.centery,
                      30, (80, 255, 120), 5.0, 35, 0.1, 4)
                self.announce_phase("+5 HP")
        self.heal_orbs[:] = [o for o in self.heal_orbs if not o.collected]

        if self.announce_t > 0: self.announce_t -= 1
        if self.flash_t > 0: self.flash_t -= 1
        if self.subtitle_t > 0: self.subtitle_t -= 1
        if self.callout_t > 0: self.callout_t -= 1

        # FINALE — SURVIE : le héros est INCREVABLE (planché à 1 PV) et la jauge
        # « ?! » se remplit en tenant bon (~28 s) jusqu'à pouvoir frapper.
        if self._finale_survival():
            if self.player.hp < 1:
                self.player.hp = 1
            self.finale_gauge = min(1.0, self.finale_gauge + 1.0 / 1680.0)

        if self.player.hp <= 0:
            self.state = STATE_GAMEOVER
            burst(self.particles, self.player.rect.centerx, self.player.rect.centery,
                  60, Pal.HP_FILL, 8.0, 50, 0.0, 5)

        if self.boss and self.boss.dead and not self.boss.final_blow_active:
            # ── Fin du combat Aegis : cinématique de fin ──────────────────
            if self.fighting_aegis:
                self.aegis_ending_t += 1
                te = self.aegis_ending_t
                if te == 1:
                    self.player.score += 5000
                # ── LE FAUX ENDING : DÈS que le texte de mort a fini de s'afficher,
                #    la fissure s'ouvre (progressivement, dans le prélude). ──
                if (te == 1000 and isinstance(self.boss, AegisBoss)
                        and not self.boss.finale_fired):
                    self.boss._start_finale(self.player, self.beams, self.projectiles_boss,
                                            self.rings, self.telegraphs, self.particles)
                    return
                # Convulsions : éruptions de lumière de + en + violentes (0→440).
                if te < 440 and te % max(3, 9 - te // 70) == 0:
                    burst(self.particles, self.boss.x + random.randint(-130, 130),
                          self.boss.y + random.randint(-130, 130),
                          26, _AEGIS_COL_DARK, 7.0, 55, 0.0, 5)
                    if te % 28 == 0:
                        self.add_shake(8 + te // 70, 14)
                # ÉCLATEMENT du dieu : déflagration colossale.
                if te == 440:
                    self.add_shake(30, 50)
                    self.flash((255, 255, 255), 26)
                    for col, spd, sz in (((255, 255, 255), 16.0, 9),
                                         (_AEGIS_COL_DARK, 12.0, 7),
                                         (_AEGIS_COL_MIXED, 9.0, 6),
                                         ((120, 12, 150), 7.0, 6)):
                        burst(self.particles, self.boss.x, self.boss.y, 120, col, spd, 80, 0.0, sz)
                # Caméra centrée sur le dieu mourant (cadrage de la cinématique).
                self.update_camera(pygame.Rect(int(self.boss.x) - 40, int(self.boss.y) - 40, 80, 80),
                                   bounds=(-220, -200, 1600, 800))
                return
            if self.aegis_dialog_active:
                self.update_aegis_dialog()
                return
            if self.final_blow_hub_t == 0:
                self.final_blow_hub_t = 1
                self.player.score += 1500
                for _ in range(8):
                    burst(self.particles, 640 + random.randint(-200, 200),
                          300 + random.randint(-150, 150),
                          40, pal_accent(self.player.dimension), 8.0, 60, 0.0, 5)
            else:
                self.final_blow_hub_t += 1
                if self.final_blow_hub_t >= 120:
                    self.start_aegis_dialog()
                    return

        self.update_camera(self.player.rect, bounds=(-220, -200, 1600, 800))
        self.starfield.update()
        self.dust.update()

    def draw_world(self, in_arena):
        dim = self.player.dimension if self.player else DIM_REAL

        # ── FINALE : le décor est LE NÉANT (noir + poussière d'étoiles). ──
        if in_arena and isinstance(self.boss, AegisBoss) and getattr(self.boss, "finale_active", False):
            self.screen.fill((6, 2, 12))
            self.starfield.draw(self.screen, self.cam, DIM_REAL)
            self._draw_finale_world()
            return

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

        # ── Fissure sur le boss (phase D2, t=201-210) ──────────────────────
        if in_arena and self.boss and self.boss_crack_active:
            bcx = int(self.boss.x - self.cam[0])
            bcy = int(self.boss.y + self.boss.float_offset - self.cam[1])
            r   = self.boss.radius
            s_crack = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
            # Fissure principale — ligne en zigzag verticale au centre
            pts = [
                (r + 4,       0),
                (r + 4 - 6,   r // 3),
                (r + 4 + 8,   r * 2 // 3),
                (r + 4 - 4,   r),
                (r + 4 + 6,   r * 4 // 3),
                (r + 4,       r * 2 + 8),
            ]
            pygame.draw.lines(s_crack, (220, 20, 10, 220), False, pts, 3)
            pygame.draw.lines(s_crack, (255, 80, 40, 120), False, pts, 6)
            # Fissures secondaires
            pygame.draw.line(s_crack, (180, 10, 10, 160),
                             (r + 4 - 6, r // 3), (r + 4 - 22, r // 3 + 14), 2)
            pygame.draw.line(s_crack, (180, 10, 10, 160),
                             (r + 4 + 8, r * 2 // 3), (r + 4 + 24, r * 2 // 3 + 10), 2)
            self.screen.blit(s_crack, (bcx - r - 4, bcy - r - 4))

        # ── Moitiés du boss fendues (phase E→F, après t=211) ───────────────
        if in_arena and self.boss_split_t > 0 and self.boss:
            sp = self.boss_split_t
            r  = self.boss.radius
            # Vitesse croissante mais plafonnée
            vel = min(sp * 0.055, 3.2)
            left_ox  = int(-sp * vel * 0.95)
            left_oy  = int( sp * vel * 0.55)
            right_ox = int( sp * vel * 0.95)
            right_oy = int( sp * vel * 0.55)
            bx = int(self.boss_split_cx - self.cam[0])
            by = int(self.boss_split_cy - self.cam[1])
            # Fondu après 50 frames
            fa = max(0, 255 - max(0, sp - 50) * 7)
            if fa > 0:
                # Surface partagée pour les deux moitiés (cercle complet)
                boss_full = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
                col_half  = (*Pal.MOON_LIGHT, fa)
                glow_col  = (*Pal.MOON_GLOW, min(60, fa // 3))
                pygame.draw.circle(boss_full, glow_col,   (r + 5, r + 5), r + 4)
                pygame.draw.circle(boss_full, col_half,   (r + 5, r + 5), r)
                # Ligne de fracture (rouge vif sur la tranche)
                pygame.draw.line(boss_full, (255, 30, 10, min(255, fa + 60)),
                                 (r + 5, 0), (r + 5, r * 2 + 10), 4)
                # Moitié gauche : area x=0 → r+5
                lx = bx + left_ox - (r + 5)
                ly = by + left_oy - (r + 5)
                self.screen.blit(boss_full, (lx, ly),
                                 area=pygame.Rect(0, 0, r + 5, r * 2 + 10))
                # Moitié droite : area x=r+5 → fin
                rx = bx + right_ox
                ry = by + right_oy - (r + 5)
                self.screen.blit(boss_full, (rx, ry),
                                 area=pygame.Rect(r + 5, 0, r + 5, r * 2 + 10))

        for tg in self.telegraphs:
            if tg.dim == dim:
                tg.draw(self.screen, self.cam)
            else:
                old = tg.color
                # Couleur alternative dimension : bleu translucide (pas gris marron)
                tg.color = (60, 100, 200)
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
        for orb in self.heal_orbs: orb.draw(self.screen, self.cam)

        if in_arena and isinstance(self.boss, MoonBoss) and self.boss.state == "fighting" and self.boss.phase == 3 and dim == DIM_REAL:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 245))   # quasi-noir en réalité seulement (rêve = visible)
            # Cercle autour du boss toujours visible
            bx_s = int(self.boss.x - self.cam[0])
            by_s = int(self.boss.y - self.cam[1])
            pygame.draw.circle(overlay, (0, 0, 0, 0), (bx_s, by_s), 140)
            # Cercle autour du joueur : seulement quand au sol ET pas en dash
            player_grounded = self.player.on_ground and self.player.dash_timer <= 0
            if player_grounded:
                sx = self.player.rect.centerx - self.cam[0]
                sy = self.player.rect.centery  - self.cam[1]
                pygame.draw.circle(overlay, (0, 0, 0, 0), (int(sx), int(sy)), 110)
            self.screen.blit(overlay, (0, 0))

        _cine = self._boss_cine_kind() if in_arena else None
        if self.player:
            # Pendant une cinématique-attaque, le héros est gelé en invuln permanent
            # → sans ça, le clignotement d'invulnérabilité le rend invisible.
            if _cine is not None:
                _sav_inv = self.player.invuln
                self.player.invuln = 0
                self.player.draw(self.screen, self.cam)
                self.player.invuln = _sav_inv
            else:
                self.player.draw(self.screen, self.cam)

        for part in self.particles: part.draw(self.screen, self.cam)

        for d in self.damage_numbers: d.draw(self.screen, self.cam)

        # ── Cinématiques-attaques scriptées (plein écran, zoom + overlays). ──
        if _cine == "nemesis":
            self._draw_nemesis()
        elif _cine == "courroux":
            self._draw_courroux()
        # ── ENTRÉE grandiose d'Aegis : cinématique d'entrée plein écran ──
        _intro = (in_arena and isinstance(self.boss, AegisBoss)
                  and self.boss.state == "intro")
        if _intro:
            self._draw_aegis_intro()

        if self.player and _cine is None and not _intro:
            self.draw_hud()
            if self.player.dimension == DIM_DREAM:
                self._draw_dream_warning()

        # Flash sortie forcée du rêve
        if self.dream_exit_flash > 0:
            self.dream_exit_flash -= 1
            fa = max(0, min(255, int(255 * self.dream_exit_flash / 12)))
            fe = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fe.fill((*Pal.D_ACCENT, fa))
            self.screen.blit(fe, (0, 0))

        # ── Phase 5 cinematic zoom ──
        if hasattr(self, 'p5_cinematic_t') and self.p5_cinematic_t > 0:
            ct = self.p5_cinematic_t
            total = 180
            # Phase A (frames 180→90): zoom in on boss
            # Phase B (frames 90→0): zoom out to arena + red flash
            if ct > 90:
                prog = (ct - 90) / 90.0   # 1.0→0.0 as we zoom in
                zoom = 1.0 + (1.0 - prog) * 1.8   # 1.0→2.8
                alpha = int(255 * (1.0 - prog))
            else:
                prog = ct / 90.0   # 1.0→0.0 as we zoom out
                zoom = 1.0 + prog * 0.6   # 1.6→1.0
                alpha = 0

            # Apply zoom: scale screen around boss position
            if self.boss and zoom > 1.01:
                bx = int(self.boss.x - self.cam[0])
                by = int(self.boss.y - self.cam[1])
                sw, sh = WIDTH, HEIGHT
                scaled_w = int(sw / zoom)
                scaled_h = int(sh / zoom)
                src_x = max(0, min(sw - scaled_w, bx - scaled_w // 2))
                src_y = max(0, min(sh - scaled_h, by - scaled_h // 2))
                sub = self.screen.subsurface(pygame.Rect(src_x, src_y, scaled_w, scaled_h))
                zoomed = pygame.transform.scale(sub.copy(), (sw, sh))
                self.screen.blit(zoomed, (0, 0))

            # Red vignette flash at peak zoom (frames ~90)
            if ct < 100 and ct > 70:
                flash_prog = 1.0 - abs(ct - 85) / 15.0
                flash_a = int(180 * flash_prog)
                flash_s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                flash_s.fill((200, 10, 20, flash_a))
                self.screen.blit(flash_s, (0, 0))

            # Fade in from black at start (frame 180→150)
            if ct > 150:
                fade_a = int(255 * (ct - 150) / 30)
                fade_s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                fade_s.fill((0, 0, 0, fade_a))
                self.screen.blit(fade_s, (0, 0))

            # Text: phase name during zoom
            if 60 < ct < 130:
                txt_alpha = min(255, int(255 * min(1.0, (ct - 60) / 20.0) * min(1.0, (130 - ct) / 20.0)))
                txt = self.font_announce.render("LE CROISSANT INVERSÉ", True, (255, 80, 60))
                txt.set_alpha(txt_alpha)
                self.screen.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

        # ── Pré-DR : overlay sombre + dialogue animé ──────────────────────────
        if in_arena and self.boss and self.boss.pre_dr_active:
            t = self.boss.pre_dr_t
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((0, 0, 0, max(0, min(255, int(140 * t / 60)))))
            self.screen.blit(s, (0, 0))
            self._draw_boss_dialog(
                ["AHHHHHH……", "TU VAS VOIR !!!"],
                t, max_t=120, angry=True
            )

        # ── Final blow cinematic ────────────────────────────────────────────────
        if in_arena and self.boss and self.boss.final_blow_active:
            t = self.boss.final_blow_t
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            # Phase A : légère vignette sombre qui s'intensifie
            if t <= 60:
                s.fill((0, 0, 0, min(120, int(120 * t / 60))))
            # Phase B : silence — vignette sombre + bord rouge pulsant
            elif t <= 110:
                prog_b = (t - 61) / 49.0
                pulse = max(0, int(25 * math.sin(t * 0.22)))
                s.fill((6, 0, 0, min(160, int(80 + 80 * prog_b))))
                pygame.draw.rect(s, (180, 10, 10, 60 + pulse), (0, 0, WIDTH, HEIGHT), 10)
            # Phase C + D + D2 + WAIT : fond sombre
            elif t <= 330:
                s.fill((0, 0, 0, 170))
            # Phase E : flash blanc à l'impact
            elif t <= 350:
                fa = max(0, min(255, int(255 * (1.0 - (t - 331) / 19.0))))
                s.fill((255, 250, 220, fa))
            # Phase F : fondu au noir progressif
            elif t <= 590:
                fa = min(255, int(255 * (t - 351) / 239.0))
                s.fill((0, 0, 0, fa))
            self.screen.blit(s, (0, 0))

            # Épée divine
            if self.sword_visible and t >= 111:
                if t <= 165:
                    prog = (t - 111) / 54.0
                elif t <= 330:
                    prog = 1.0
                else:
                    prog = 0.0
                self._draw_divine_sword(self.sword_x, self.sword_y, prog)

            # ── Point d'interrogation sur le boss (phase WAIT 211-330) ──────
            if self.boss_qmark_t > 0:
                qm_t = self.boss_qmark_t
                # Apparition progressive (fondu sur 30 frames)
                qm_alpha = min(255, int(255 * qm_t / 30))
                # Légère oscillation verticale
                boss_sx = int(self.boss.x - self.cam[0])
                boss_sy = int(self.boss.y - self.cam[1])
                qm_y = boss_sy - 90 - int(8 * math.sin(qm_t * 0.07))
                # Rendu du "?" avec la police
                qm_surf = self.font_big.render("?", True, (255, 230, 60))
                qm_surf.set_alpha(qm_alpha)
                # Contour sombre pour lisibilité
                qm_shadow = self.font_big.render("?", True, (20, 10, 0))
                qm_shadow.set_alpha(qm_alpha)
                self.screen.blit(qm_shadow, (boss_sx - qm_surf.get_width() // 2 + 2,
                                             qm_y + 2))
                self.screen.blit(qm_surf, (boss_sx - qm_surf.get_width() // 2, qm_y))

        # (overlay victoire géré dans la boucle principale, pas ici)

        # ── Post-DR dialogue ────────────────────────────────────────────────────
        if in_arena and self.post_dr_dialog_t > 0:
            self.post_dr_dialog_t += 1
            self._draw_boss_dialog(
                ["…TU T'EN SORTIRAS PAS.", "JE SUIS INDESTRUCTIBLE."],
                self.post_dr_dialog_t, max_t=200, angry=False
            )
            if self.post_dr_dialog_t >= 200:
                self.post_dr_dialog_t = 0

        # ── Derniers Recours cinematic overlay ──
        if in_arena and self.boss and self.boss.last_resort_active:
            t = self.boss.last_resort_t
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            if t < 50:
                # Vignette rouge qui s'intensifie
                va = max(0, min(255, int(60 * t / 50)))
                pygame.draw.rect(s, (180, 10, 10, va), (0, 0, WIDTH, HEIGHT), max(6, 80 - t))
            elif t < 110:
                # Écran qui se noircit quand le boss sort
                prog = (t - 50) / 60.0
                va = max(0, min(255, int(120 * prog)))
                s.fill((0, 0, 0, va))
            elif t < 155:
                # Vide : écran très sombre avec pulsation rouge
                pulse = max(0, min(255, int(30 + 20 * math.sin(t * 0.25))))
                s.fill((8, 0, 0, 200))
                pygame.draw.rect(s, (200, 0, 0, pulse), (0, 0, WIDTH, HEIGHT), 8)
            elif t < 185:
                # Retour : vignette rouge qui s'estompe
                prog = (t - 155) / 30.0
                va = max(0, int(160 * (1 - prog)))
                s.fill((0, 0, 0, max(0, int(100 * (1 - prog)))))
                pygame.draw.rect(s, (255, 20, 0, va), (0, 0, WIDTH, HEIGHT), 6)
            elif t < 200:
                # Flash blanc-rouge au moment de l'impact
                fa = int(255 * max(0, 1.0 - (t - 185) / 15.0))
                s.fill((255, 60, 20, fa))
            self.screen.blit(s, (0, 0))

        # ── L'Enchaînement Divin : cadrage CINÉMATIQUE (façon combat de Sans) ─
        if in_arena and isinstance(self.boss, AegisBoss) and self.boss._cine_active:
            ct = self.boss._cine_t
            cd = max(1, self.boss._cine_dur)
            bar_max = 58
            # Bandes letterbox : entrée (0→16), tenue, sortie (cd-26→cd).
            if ct < 16:
                bar_h = int(bar_max * ct / 16)
            elif ct > cd - 26:
                bar_h = int(bar_max * max(0, cd - ct) / 26)
            else:
                bar_h = bar_max
            # Vignette magenta « dread » qui respire avec la même enveloppe.
            env = (min(1.0, ct / 16.0) if ct < 16
                   else (max(0.0, (cd - ct) / 26.0) if ct > cd - 26 else 1.0))
            vig_a = int(70 * env)
            if vig_a > 0:
                vg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(vg, (120, 10, 90, vig_a), (0, 0, WIDTH, HEIGHT), 110)
                self.screen.blit(vg, (0, 0))
            if bar_h > 0:
                gl = max(0, min(255, int(150 + 90 * math.sin(ct * 0.2))))
                top_bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
                top_bar.fill((6, 2, 10, 238))
                pygame.draw.line(top_bar, (235, 40, 165, gl),
                                 (0, bar_h - 1), (WIDTH, bar_h - 1), 2)
                self.screen.blit(top_bar, (0, 0))
                bot_bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
                bot_bar.fill((6, 2, 10, 238))
                pygame.draw.line(bot_bar, (235, 40, 165, gl), (0, 0), (WIDTH, 0), 2)
                self.screen.blit(bot_bar, (0, HEIGHT - bar_h))
            # Titre claqué dans la bande haute : punch-in puis estompe.
            if bar_h > 12 and ct < cd - 26:
                if ct < 10:
                    title_a = int(255 * ct / 10)
                elif ct > 96:
                    title_a = max(60, 255 - int((ct - 96) * 1.8))
                else:
                    title_a = 255
                name = self.boss._cine_name
                ts = self.font_announce.render(name, True, (255, 222, 246))
                sh = self.font_announce.render(name, True, (45, 4, 32))
                ts.set_alpha(title_a); sh.set_alpha(title_a)
                tr = ts.get_rect(center=(WIDTH // 2, 27))
                self.screen.blit(sh, (tr.x + 2, tr.y + 2))
                self.screen.blit(ts, tr)
                # Chevrons latéraux qui pointent vers le titre.
                cyl = 27
                for sgn, x0 in ((-1, tr.left - 26), (1, tr.right + 26)):
                    pygame.draw.polygon(self.screen, (255, 95, 215, title_a),
                        [(x0, cyl - 9), (x0 + sgn * 13, cyl), (x0, cyl + 9)])
            # Compteur de vagues dans la bande basse (pips chevrons).
            if bar_h > 12:
                wv = self.boss._cine_wave; wt = max(1, self.boss._cine_waves)
                pip_y = HEIGHT - bar_h // 2
                x0 = WIDTH // 2 - (wt - 1) * 13
                for i in range(wt):
                    cxp = x0 + i * 26
                    on = i < wv
                    col = (255, 95, 215) if on else (96, 44, 86)
                    pts = [(cxp - 7, pip_y + 6), (cxp, pip_y - 7), (cxp + 7, pip_y + 6)]
                    pygame.draw.polygon(self.screen, col, pts)
                    if on:
                        pygame.draw.polygon(self.screen, (255, 236, 250), pts, 1)

    # ── NÉMÉSIS : rendu de la cinématique d'ouverture de la phase 7 ─────────
    def _blit_star(self, surf, cx, cy, r_out, r_in, color, glow=None, a=255,
                   points=5, rot=0.0):
        """Étoile additive (pour les yeux rouges d'Aegis)."""
        r_out = max(2.0, r_out); r_in = max(1.0, r_in)
        side = int(r_out * 2 + 10)
        s = pygame.Surface((side, side), pygame.SRCALPHA)
        c = side / 2.0
        if glow:
            pygame.draw.circle(s, (*glow, int(a * 0.45)), (int(c), int(c)), int(r_out))
        pts = []
        for i in range(points * 2):
            rr = r_out if i % 2 == 0 else r_in
            ang = rot - math.pi / 2 + i * math.pi / points
            pts.append((c + math.cos(ang) * rr, c + math.sin(ang) * rr))
        pygame.draw.polygon(s, (*color, max(0, min(255, a))), pts)
        surf.blit(s, (cx - c, cy - c), special_flags=pygame.BLEND_RGBA_ADD)

    def _blit_black_hole(self, surf, cx, cy, R, frame):
        """Trou noir : halo gravitationnel + cœur opaque + disque d'accrétion +
        double spirale contrarotative + anneau de lentille incandescent."""
        R = max(4, int(R))
        side = R * 6
        s = pygame.Surface((side, side), pygame.SRCALPHA)
        c = side // 2
        # Halo gravitationnel diffus (lumière courbée alentour).
        for k in range(6):
            rr = int(R * (2.2 - k * 0.3))
            if rr <= 0: continue
            pygame.draw.circle(s, (120, 14, 96, max(0, 24 - k * 3)), (c, c), rr)
        # Disque d'accrétion magenta (anneaux brillants).
        for k in range(4):
            aa = max(0, int(180 - k * 42))
            pygame.draw.circle(s, (205, 30, 156, aa), (c, c), R + 6 + k * 7, 3)
        # Double spirale contrarotative.
        for i in range(20):
            a = i * math.tau / 20 + frame * 0.09
            x1 = c + math.cos(a) * (R + 34); y1 = c + math.sin(a) * (R + 34)
            x2 = c + math.cos(a + 0.6) * (R * 0.45); y2 = c + math.sin(a + 0.6) * (R * 0.45)
            pygame.draw.line(s, (170, 36, 132, 120), (x1, y1), (x2, y2), 2)
        for i in range(14):
            a = -i * math.tau / 14 - frame * 0.05
            x1 = c + math.cos(a) * (R + 18); y1 = c + math.sin(a) * (R + 18)
            x2 = c + math.cos(a + 0.5) * (R * 0.6); y2 = c + math.sin(a + 0.5) * (R * 0.6)
            pygame.draw.line(s, (235, 60, 180, 90), (x1, y1), (x2, y2), 1)
        # Cœur opaque (le vide absolu).
        for k in range(6):
            rr = int(R * (1.0 - k / 7.0))
            if rr <= 0: continue
            col = (3, 0, 6, 255) if k == 0 else (10, 0, 16, max(120, 225 - k * 20))
            pygame.draw.circle(s, col, (c, c), rr)
        # Anneau de lentille : fine ligne incandescente au bord de l'horizon.
        glow = max(0, min(255, int(180 + 60 * math.sin(frame * 0.18))))
        pygame.draw.circle(s, (255, 90, 205, glow), (c, c), R + 2, 2)
        surf.blit(s, (cx - c, cy - c))

    def _blit_white_hole(self, surf, cx, cy, R, frame):
        """Trou blanc : noyau éblouissant + halo radiant pulsé + couronne de
        rayons jaillissants (longs + courts) + anneau de choc."""
        R = max(4, int(R))
        side = R * 6
        s = pygame.Surface((side, side), pygame.SRCALPHA)
        c = side // 2
        # Halo radiant en dégradé.
        for k in range(9):
            rr = int(R * (2.0 - k * 0.18))
            if rr <= 0: continue
            pygame.draw.circle(s, (255, 250, 240, int(20 + 16 * k)), (c, c), rr)
        # Rayons longs jaillissants (rotation lente).
        for i in range(16):
            a = i * math.tau / 16 - frame * 0.06
            r1 = R + 44 + 16 * math.sin(frame * 0.18 + i)
            x2 = c + math.cos(a) * r1; y2 = c + math.sin(a) * r1
            pygame.draw.line(s, (255, 255, 245, 150), (c, c), (x2, y2), 2)
        # Rayons courts intercalés (contre-rotation).
        for i in range(16):
            a = i * math.tau / 16 + math.pi / 16 + frame * 0.04
            r1 = R + 22 + 8 * math.sin(frame * 0.25 + i)
            x2 = c + math.cos(a) * r1; y2 = c + math.sin(a) * r1
            pygame.draw.line(s, (255, 240, 220, 110), (c, c), (x2, y2), 1)
        # Anneau de choc.
        pul = max(0, min(255, int(150 + 80 * math.sin(frame * 0.2))))
        pygame.draw.circle(s, (255, 255, 250, pul), (c, c), R + 10, 2)
        # Noyau éblouissant.
        pygame.draw.circle(s, (255, 255, 255, 255), (c, c), int(R * 0.72))
        surf.blit(s, (cx - c, cy - c), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_nemesis(self):
        """Cinématique NÉMÉSIS (ouverture phase 7), 50 s, entièrement scriptée.
        Couches : (1) FX en espace-monde, (2) ZOOM dynamique (keyframes lissées),
        (3) surcouches plein écran (letterbox, titre, répliques, flashs)."""
        boss = self.boss
        scr = self.screen
        t = boss.nemesis_t
        T = boss.nemesis_dur
        W, H = WIDTH, HEIGHT
        cam = self.cam
        fr = self.frame
        (B_EYES, B_GRAB, B_LIFT, B_BLACK, B_WHITE, B_FACE, B_TAUNT,
         B_CHARGE, B_LASER, B_SLAM, B_EXHAUST, B_CONVERGE, B_BOOM) = boss._nem_beats()

        def _ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)   # smootherstep quintique

        # Coordonnées écran (caméra figée à 0,0 pendant NÉMÉSIS).
        bx = int(boss.x - cam[0]); by = int(boss.y + boss.float_offset - cam[1])
        px = int(boss._nem_px - cam[0]); py = int(boss._nem_py - cam[1])
        black = (int(boss.cx + 520 - cam[0]), int(boss.target_y + 40 - cam[1]))
        white = (int(boss.cx - 520 - cam[0]), int(boss.target_y + 40 - cam[1]))
        # Ancrages mains/yeux proportionnels à la taille (agrandie) du sprite.
        hox = int(boss.vis * 0.58); hoy = int(boss.vis * 0.47); eyo = int(boss.vis * 0.28)

        # Naissance lissée des trous.
        kb = _ease((t - B_LIFT) / float(B_BLACK - B_LIFT)) if t > B_LIFT else 0.0
        kw = _ease((t - B_BLACK) / float(B_WHITE - B_BLACK)) if t > B_BLACK else 0.0
        # Convergence : les trous foncent sur le héros entre CONVERGE et BOOM.
        if B_CONVERGE < t <= B_BOOM:
            rush = _ease((t - B_CONVERGE) / float(B_BOOM - B_CONVERGE))
        else:
            rush = 1.0 if t > B_BOOM else 0.0
        bpos = (int(black[0] + (px - black[0]) * rush), int(black[1] + (py - black[1]) * rush))
        wpos = (int(white[0] + (px - white[0]) * rush), int(white[1] + (py - white[1]) * rush))

        # ============ 1) FX en espace-monde (capturés par le zoom) ============
        # Lueur de charge dans les mains d'Aegis (éveil → arrachage).
        if B_EYES < t <= B_LIFT:
            cg = _ease((t - B_EYES) / float(B_GRAB - B_EYES)) if t <= B_GRAB else 1.0
            rad = int(14 + 10 * cg + 4 * math.sin(fr * 0.4))
            hs = pygame.Surface((rad * 2 + 6, rad * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(hs, (235, 60, 180, int(150 * cg)), (rad + 3, rad + 3), rad)
            pygame.draw.circle(hs, (255, 210, 245, int(180 * cg)), (rad + 3, rad + 3), max(2, rad // 2))
            for sgn in (-1, 1):
                scr.blit(hs, (bx + sgn * hox - rad - 3, by + hoy - rad - 3),
                         special_flags=pygame.BLEND_RGBA_ADD)

        # Liens télékinésiques : les mains d'Aegis tiennent le héros en l'air.
        if t > B_GRAB - 30:
            grip = min(1.0, (t - (B_GRAB - 30)) / 50.0)
            for sgn in (-1, 1):
                hx = bx + sgn * hox; hy = by + hoy
                perp = math.atan2(py - hy, px - hx) + math.pi / 2
                pts = [(hx, hy)]
                for sgi in range(1, 9):
                    f = sgi / 9.0
                    wob = math.sin(fr * 0.25 + sgi * 1.3 + sgn) * 7 * (1 - abs(f - 0.5) * 2)
                    nx = hx + (px - hx) * f; ny = hy + (py - hy) * f
                    pts.append((nx + math.cos(perp) * wob, ny + math.sin(perp) * wob))
                pts.append((px, py))
                pygame.draw.lines(scr, (235, 40, 165), False, pts, max(2, int(4 * grip)))
                pygame.draw.lines(scr, (255, 180, 235), False, pts, max(1, int(2 * grip)))
            gr = 52
            gs = pygame.Surface((gr * 2 + 8, gr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(gs, (235, 40, 165, int(110 * grip)), (gr + 4, gr + 4), gr, 4)
            pygame.draw.circle(gs, (255, 150, 225, int(70 * grip)), (gr + 4, gr + 4), gr - 8, 2)
            scr.blit(gs, (px - gr - 4, py - gr - 4), special_flags=pygame.BLEND_RGBA_ADD)

        # Yeux-étoiles ROUGES d'Aegis (allumage progressif dès le tout début).
        if t > 4:
            eg = min(1.0, t / 60.0)
            er = (11 + 5 * math.sin(fr * 0.3)) * eg
            for sgn in (-1, 1):
                self._blit_star(scr, bx + sgn * eyo, by - eyo, er * 2.4, er * 0.95,
                                (255, 30, 30), glow=(255, 90, 60), a=int(240 * eg),
                                rot=fr * 0.05)

        # Télégraphe d'implosion AVANT chaque trou (anneau qui se referme).
        def _implosion_tell(cxp, cyp, t0, t1, col):
            if t0 < t < t1:
                u = (t - t0) / float(t1 - t0)
                rr = int(150 * (1 - u)) + 30
                aa = int(160 * (1 - abs(u - 0.5) * 2))
                if aa <= 0 or rr <= 0: return
                ts2 = pygame.Surface((rr * 2 + 8, rr * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(ts2, (*col, max(0, aa)), (rr + 4, rr + 4), rr, 3)
                scr.blit(ts2, (cxp - rr - 4, cyp - rr - 4), special_flags=pygame.BLEND_RGBA_ADD)
        _implosion_tell(black[0], black[1], B_LIFT, B_BLACK, (210, 40, 150))
        _implosion_tell(white[0], white[1], B_BLACK, B_WHITE, (255, 250, 235))

        # Trou noir (droite) puis trou blanc (gauche) — grossissent puis foncent.
        if kb > 0:
            self._blit_black_hole(scr, bpos[0], bpos[1], int(98 * kb), fr)
        if kw > 0:
            self._blit_white_hole(scr, wpos[0], wpos[1], int(98 * kw), fr)

        # Plateformes CONJURÉES par Aegis (surfaces d'impact, façon Sans).
        if boss._nem_slabs and t < B_BOOM + 30:
            sl_fade = max(0.0, 1.0 - (t - B_BOOM) / 30.0) if t >= B_BOOM else 1.0
            for (scx, scy, sw, sh, sbirth, shit) in boss._nem_slabs:
                ap = min(1.0, (t - sbirth) / 8.0)
                if ap <= 0: continue
                w = int(sw * ap * sl_fade); h = int(sh * sl_fade)
                if w < 4 or h < 2: continue
                rx = int(scx - cam[0] - w / 2); ry = int(scy - cam[1] - h / 2)
                pygame.draw.rect(scr, (24, 4, 18), (rx, ry, w, h), border_radius=5)
                pygame.draw.rect(scr, (235, 40, 165), (rx, ry, w, h), 3, border_radius=5)
                pygame.draw.line(scr, (255, 150, 225), (rx + 5, ry + 2), (rx + w - 5, ry + 2), 2)
                if shit >= 0:                                   # fissures de fracas
                    cxm = rx + w // 2; cym = ry + h // 2
                    for ddx in (-1, 1):
                        pygame.draw.line(scr, (255, 210, 245), (cxm, cym),
                                         (cxm + ddx * w // 3, ry - 5), 2)
                        pygame.draw.line(scr, (255, 210, 245), (cxm, cym),
                                         (cxm + ddx * w // 4, ry + h + 5), 2)

        # PICS du SOL (ACT IV) — jaillissent UNIQUEMENT du sol, pointe vers le haut.
        if boss._nem_spikes and t < B_BOOM + 30:
            sp_fade = max(0.0, 1.0 - (t - B_BOOM) / 30.0) if t >= B_BOOM else 1.0
            for (sbx, sby, sang, slen, sbirth) in boss._nem_spikes:
                grow = min(1.0, (t - sbirth) / 9.0)
                L = slen * grow * sp_fade
                if L < 2: continue
                ang = math.radians(sang); perp = ang + math.pi / 2
                hw = L * 0.22
                bxs = sbx - cam[0]; bys = sby - cam[1]
                tip = (bxs + math.cos(ang) * L, bys + math.sin(ang) * L)
                b1 = (bxs + math.cos(perp) * hw, bys + math.sin(perp) * hw)
                b2 = (bxs - math.cos(perp) * hw, bys - math.sin(perp) * hw)
                pygame.draw.polygon(scr, (38, 4, 24), [b1, b2, tip])
                pygame.draw.polygon(scr, (235, 40, 165), [b1, b2, tip], 2)
                pygame.draw.line(scr, (255, 150, 225),
                                 ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2), tip, 2)

        # IMPACT BRUTAL : éclat radial blanc + anneau de choc (façon Sans).
        ii = t - boss._nem_impact_t
        if 0 <= ii < 12:
            ix = boss._nem_impact_xy[0] - cam[0]; iy = boss._nem_impact_xy[1] - cam[1]
            kf2 = 1 - ii / 12.0
            isurf = pygame.Surface((W, H), pygame.SRCALPHA)
            for ai in range(12):
                a = ai * math.tau / 12 + boss._nem_impact_t * 0.7
                L = 36 + 150 * (1 - kf2)
                pygame.draw.line(isurf, (255, 255, 255, max(0, int(220 * kf2))),
                                 (ix, iy), (ix + math.cos(a) * L, iy + math.sin(a) * L),
                                 max(2, int(6 * kf2)))
            pygame.draw.circle(isurf, (255, 200, 240, max(0, int(170 * kf2))),
                               (int(ix), int(iy)), int(24 + 110 * (1 - kf2)), max(2, int(6 * kf2)))
            scr.blit(isurf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # ── LASERS : charge (windup) puis 4 faisceaux imposants ──
        laser_dirs = [i * math.tau / 4 + 0.4 + t * 0.003 for i in range(4)]
        # (a) Windup : réticules + rais de visée qui se chargent.
        if B_CHARGE < t <= B_LASER:
            cu = _ease((t - B_CHARGE) / float(B_LASER - B_CHARGE))
            cs = pygame.Surface((W, H), pygame.SRCALPHA)
            for a in laser_dirs:
                sx = int(px + math.cos(a) * 380); sy = int(py + math.sin(a) * 380)
                pygame.draw.line(cs, (255, 120, 220, int(160 * cu)), (sx, sy), (px, py),
                                 max(1, int(1 + 3 * cu)))
                nr = int(8 + 18 * cu + 3 * math.sin(fr * 0.6))
                pygame.draw.circle(cs, (255, 90, 210, int(170 * cu)), (sx, sy), nr)
                pygame.draw.circle(cs, (255, 235, 250, int(220 * cu)), (sx, sy), max(2, nr // 2))
            scr.blit(cs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        # (b) SPAM de lasers (ACT III) : salves successives, de + en + nombreuses.
        if B_LASER < t <= B_SLAM:
            prog = (t - B_LASER) / float(B_SLAM - B_LASER)
            fire = min(1.0, (t - B_LASER) / 16.0)
            fade = max(0.0, (B_SLAM - t) / 26.0) if t > B_SLAM - 26 else 1.0
            amp = fire * fade
            n = 4 + 2 * min(2, int(prog * 3))                # 4 → 6 → 8 faisceaux
            vp = 26                                           # période d'une salve
            ph = (t - B_LASER) % vp
            volley = 1.0 - ph / float(vp)                     # 1 juste après le tir → 0
            flash = max(0.0, 1.0 - ph / 7.0)                  # éclair bref au tir
            base = 0.4 + t * 0.018                            # rotation frénétique
            ls = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(n):
                a = base + i * math.tau / n
                sx = px + math.cos(a) * 1100; sy = py + math.sin(a) * 1100
                pulse = 1.0 + 0.22 * math.sin(fr * 0.5 + i)
                wide = max(6, int((24 + 14 * volley) * amp * pulse))
                mid = max(3, int((13 + 6 * volley) * amp)); core = max(1, int(6 * amp))
                pygame.draw.line(ls, (190, 30, 150, int(80 * amp)), (sx, sy), (px, py), wide)
                pygame.draw.line(ls, (255, 80, 210, int(160 * amp)), (sx, sy), (px, py), mid)
                pygame.draw.line(ls, (255, 240, 252, int(225 * amp)), (sx, sy), (px, py), core)
            br = (44 + 30 * volley) * amp                     # bloom pulsé par salve
            pygame.draw.circle(ls, (255, 120, 225, int(150 * amp)), (px, py), max(8, int(br)))
            pygame.draw.circle(ls, (255, 250, 255, int(210 * amp)), (px, py), max(4, int(br * 0.5)))
            scr.blit(ls, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            if flash > 0 and amp > 0:                         # éclair plein écran au tir
                fla = pygame.Surface((W, H), pygame.SRCALPHA)
                fla.fill((255, 120, 220, int(40 * flash * amp)))
                scr.blit(fla, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Noyau de broyage : incandescence qui enfle quand les trous se rejoignent.
        if B_CONVERGE < t <= B_BOOM:
            cr = int(24 + 130 * rush)
            cs2 = pygame.Surface((cr * 2 + 8, cr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(cs2, (255, 255, 255, int(210 * rush)), (cr + 4, cr + 4), cr)
            pygame.draw.circle(cs2, (235, 40, 165, int(160 * rush)), (cr + 4, cr + 4), cr, 6)
            scr.blit(cs2, (px - cr - 4, py - cr - 4), special_flags=pygame.BLEND_RGBA_ADD)

        # Ondes de choc de la détonation (déflagration en anneaux).
        if B_BOOM <= t < B_BOOM + 110:
            for k in range(3):
                d = (t - B_BOOM) - k * 12
                if d <= 0: continue
                rr = int(d * 9); aa = max(0, int(200 - d * 2))
                if aa <= 0 or rr <= 0: continue
                col = (255, 255, 255) if k == 0 else ((235, 40, 165) if k == 1 else (120, 12, 150))
                sw = pygame.Surface((rr * 2 + 10, rr * 2 + 10), pygame.SRCALPHA)
                pygame.draw.circle(sw, (*col, aa), (rr + 5, rr + 5), rr, max(2, 8 - k * 2))
                scr.blit(sw, (px - rr - 5, py - rr - 5), special_flags=pygame.BLEND_RGBA_ADD)

        # ============ 2) ZOOM dynamique (keyframes lissées) ============
        # Chaque keyframe = (frame, focus_x, focus_y, zoom). Interpolation
        # smootherstep entre keyframes → pas de saccade aux jointures.
        eyes_pt = (bx, by - 26)
        grab_pt = ((bx + px) / 2, (by + py) / 2 + 8)
        hero_pt = (px, py)
        mid_pt = ((bx + px) / 2, (by + py) / 2 + 4)
        kf = [
            (0,          eyes_pt[0], eyes_pt[1], 1.00),
            (B_EYES,     eyes_pt[0], eyes_pt[1], 1.55),
            (B_GRAB,     grab_pt[0], grab_pt[1], 2.00),
            (B_LIFT,     hero_pt[0], hero_pt[1], 2.15),
            (B_BLACK,    black[0],   black[1],   2.45),
            (B_WHITE,    white[0],   white[1],   2.40),   # swoosh droite→gauche
            (B_FACE,     mid_pt[0],  mid_pt[1],  2.10),
            (B_TAUNT,    hero_pt[0], hero_pt[1], 1.95),
            (B_CHARGE,   hero_pt[0], hero_pt[1], 1.92),
            (B_LASER,    hero_pt[0], hero_pt[1], 1.85),
            (B_SLAM,     hero_pt[0], hero_pt[1], 1.55),   # suit le pantin (large)
            (B_EXHAUST,  hero_pt[0], hero_pt[1], 1.60),
            (B_CONVERGE, hero_pt[0], hero_pt[1], 1.95),
            (B_BOOM,     hero_pt[0], hero_pt[1], 2.65),
            (T,          hero_pt[0], hero_pt[1], 1.00),
        ]
        fx, fy, zoom = hero_pt[0], hero_pt[1], 1.0
        for i in range(len(kf) - 1):
            t0, fx0, fy0, z0 = kf[i]; t1, fx1, fy1, z1 = kf[i + 1]
            if t0 <= t <= t1:
                e = _ease((t - t0) / float(max(1, t1 - t0)))
                fx = fx0 + (fx1 - fx0) * e
                fy = fy0 + (fy1 - fy0) * e
                zoom = z0 + (z1 - z0) * e
                break

        si = t - boss._nem_impact_t                     # secousse d'impact du pantin
        if 0 <= si < 16:
            amp = 34 * (1 - si / 16.0)                  # cogne fort (façon Sans)
            fx += random.uniform(-amp, amp); fy += random.uniform(-amp, amp)
            if si < 8:                                  # coup de zoom sec à l'impact
                zoom *= 1.0 + 0.13 * (1 - si / 8.0)
        if B_CONVERGE < t < B_BOOM + 30:                # secousse de détonation
            amp = 12 * max(rush, 0.4)
            fx += random.uniform(-amp, amp); fy += random.uniform(-amp, amp)

        if zoom > 1.01:
            scaled_w = max(2, int(W / zoom)); scaled_h = max(2, int(H / zoom))
            src_x = max(0, min(W - scaled_w, int(fx) - scaled_w // 2))
            src_y = max(0, min(H - scaled_h, int(fy) - scaled_h // 2))
            sub = scr.subsurface(pygame.Rect(src_x, src_y, scaled_w, scaled_h))
            scr.blit(pygame.transform.scale(sub.copy(), (W, H)), (0, 0))

        # ============ 3) Surcouches plein écran (non zoomées) =================
        bar_max = 70
        if t < 30:
            bar_h = int(bar_max * t / 30)
        elif t > T - 50:
            bar_h = int(bar_max * max(0, T - t) / 50)
        else:
            bar_h = bar_max
        if bar_h > 0:
            for yb in (0, H - bar_h):
                bar = pygame.Surface((W, bar_h), pygame.SRCALPHA)
                bar.fill((4, 0, 6, 240))
                ly = bar_h - 1 if yb == 0 else 0
                pygame.draw.line(bar, (200, 20, 40), (0, ly), (W, ly), 2)
                scr.blit(bar, (0, yb))

        if B_BLACK < t <= B_WHITE:                      # stries de vitesse (swoosh)
            sw_a = int(160 * (1 - abs((t - B_BLACK) / float(B_WHITE - B_BLACK) - 0.5) * 2))
            if sw_a > 0:
                ss = pygame.Surface((W, H), pygame.SRCALPHA)
                for k in range(24):
                    yy = (k * 33 + fr * 46) % H
                    pygame.draw.line(ss, (255, 255, 255, max(0, sw_a)), (0, yy), (W, yy), 2)
                scr.blit(ss, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Vignette rouge — se renforce pendant la charge/le broyage.
        env = (min(1.0, t / 30.0) if t < 30
               else (max(0.0, (T - t) / 50.0) if t > T - 50 else 1.0))
        vig = 70
        if B_CHARGE < t < B_BOOM:
            vig = 70 + int(60 * min(1.0, (t - B_CHARGE) / float(B_BOOM - B_CHARGE)))
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vg, (120, 0, 20, max(0, int(vig * env))), (0, 0, W, H), 120)
        scr.blit(vg, (0, 0))

        if t < B_LIFT and bar_h > 16:                   # titre « NÉMÉSIS »
            if t < 18: ta = int(255 * t / 18)
            elif t > B_GRAB: ta = max(0, 255 - int((t - B_GRAB) * 1.6))
            else: ta = 255
            if ta > 0:
                nm = self.font_announce.render("NÉMÉSIS", True, (255, 60, 60))
                sh2 = self.font_announce.render("NÉMÉSIS", True, (40, 0, 0))
                nm.set_alpha(ta); sh2.set_alpha(ta)
                rr = nm.get_rect(center=(W // 2, bar_max // 2 + 4))
                scr.blit(sh2, (rr.x + 3, rr.y + 3)); scr.blit(nm, rr)

        if B_TAUNT - 40 < t < B_LASER + 20:             # réplique « TU ME FATIGUES »
            qa = min(255, int(255 * min(1.0, (t - (B_TAUNT - 40)) / 26.0)))
            if t > B_LASER - 30:
                qa = max(0, int(255 * (1.0 - (t - (B_LASER - 30)) / 50.0)))
            if qa > 0:
                self._cine_voice_once(("nm", "fatigues"), _VOICE_AEGIS_VOID)
                line = self.font_big.render("« TU ME FATIGUES. »", True, (255, 225, 235))
                lsh = self.font_big.render("« TU ME FATIGUES. »", True, (60, 0, 20))
                line.set_alpha(qa); lsh.set_alpha(qa)
                lr = line.get_rect(center=(W // 2, H - bar_max // 2 - 6))
                scr.blit(lsh, (lr.x + 2, lr.y + 2)); scr.blit(line, lr)

        if B_BOOM <= t < B_BOOM + 46:                   # flash blanc d'explosion
            fa = max(0, int(255 * (1.0 - (t - B_BOOM) / 46.0)))
            fs = pygame.Surface((W, H)); fs.fill((255, 255, 255)); fs.set_alpha(fa)
            scr.blit(fs, (0, 0))

        # « TU ES FINIS !!! » — CRI final plein écran (détonation → fin).
        if t >= B_BOOM:
            self._cine_voice_once(("nm", "finis"), _VOICE_AEGIS_VOID)
            sc = min(1.0, (t - B_BOOM) / 18.0)
            txt = "TU ES FINIS !!!"
            base_txt = self.font_big.render(txt, True, (255, 40, 40))
            sh_txt = self.font_big.render(txt, True, (25, 0, 0))
            target_w = (W - 80) * (0.70 + 0.30 * sc)
            scale = (target_w / base_txt.get_width()) * (1.0 + 0.03 * math.sin(fr * 0.5))
            bw = max(1, int(base_txt.get_width() * scale))
            bh = max(1, int(base_txt.get_height() * scale))
            big = pygame.transform.smoothscale(base_txt, (bw, bh))
            bsh = pygame.transform.smoothscale(sh_txt, (bw, bh))
            aaa = max(0, min(255, int(255 * sc)))
            big.set_alpha(aaa); bsh.set_alpha(aaa)
            shx = random.randint(-7, 7); shy = random.randint(-7, 7)
            rr = big.get_rect(center=(W // 2 + shx, H // 2 + shy))
            scr.blit(bsh, (rr.x + 5, rr.y + 5)); scr.blit(big, rr)

        if t < 20:                                      # fondu d'entrée (depuis le noir)
            fa = int(210 * (1 - t / 20.0))
            fs = pygame.Surface((W, H)); fs.fill((0, 0, 0)); fs.set_alpha(fa)
            scr.blit(fs, (0, 0))

    def _draw_courroux(self):
        """COURROUX (attaque phase 4, 50 s) : rupture du masque → pression →
        déluge de météores → écrasement colossal → verdict. Rage. Brutalité. Puissance."""
        boss = self.boss; scr = self.screen
        t = boss.courroux_t; T = boss.courroux_dur
        W, H = WIDTH, HEIGHT; cam = self.cam; fr = self.frame
        (B_SHATTER, B_ROAR, B_PRESSURE, B_STORM, B_RAISE, B_SLAM, B_VERDICT) = boss._cx_beats()

        def ease(u):
            u = 0.0 if u < 0 else (1.0 if u > 1 else u)
            return u * u * u * (u * (u * 6 - 15) + 10)

        bx = int(boss.x - cam[0]); by = int(boss.y + boss.float_offset - cam[1])
        px = int(boss._cx_gx - cam[0]); py = int(boss._cx_gy - cam[1])
        cxs = int(boss.cx - cam[0]); floor_y = 632 - int(cam[1])
        eyo = int(boss.vis * 0.28)

        # ════════ 1) FX en espace-monde (captés par le zoom) ════════
        # Aura de rage : halo sombre pulsant derrière Aegis (puissance brute).
        au = 0.4 + 0.6 * ease(min(1.0, t / float(B_ROAR)))
        ar = int(boss.vis * (1.15 + 0.08 * math.sin(fr * 0.2)) * au)
        aus = pygame.Surface((ar * 2 + 8, ar * 2 + 8), pygame.SRCALPHA)
        for k in range(4):
            pygame.draw.circle(aus, (150, 16, 96, max(0, int(40 - k * 8))),
                               (ar + 4, ar + 4), int(ar * (1 - k * 0.16)))
        scr.blit(aus, (bx - ar - 4, by - ar - 4), special_flags=pygame.BLEND_RGBA_ADD)

        # Fissures du masque AVANT la rupture (lézardes dorées sur le visage).
        if t < B_SHATTER:
            ck = ease(t / float(B_SHATTER))
            for i in range(6):
                a0 = -math.pi / 2 + (i - 2.5) * 0.5
                x0 = bx + math.cos(a0) * eyo * 0.4
                y0 = by - eyo
                L = (16 + 60 * ck)
                pygame.draw.line(scr, (255, 226, 150),
                                 (int(x0), int(y0)),
                                 (int(x0 + math.cos(a0) * L), int(y0 + math.sin(a0) * L)),
                                 max(1, int(1 + 2 * ck)))

        # Yeux-étoiles ROUGES : la vraie face, ignée de rage (après la rupture).
        if t >= B_SHATTER:
            eg = min(1.0, (t - B_SHATTER) / 50.0)
            er = (12 + 6 * math.sin(fr * 0.3)) * eg
            for sgn in (-1, 1):
                self._blit_star(scr, bx + sgn * eyo, by - eyo, er * 2.5, er * 0.95,
                                (255, 26, 26), glow=(255, 90, 60), a=int(245 * eg), rot=fr * 0.05)

        # ACT II — PRESSION : anneaux gravitationnels qui se resserrent + plaque-sol.
        if B_PRESSURE <= t < B_STORM:
            pu = (t - B_PRESSURE) / float(B_STORM - B_PRESSURE)
            ps = pygame.Surface((W, H), pygame.SRCALPHA)
            for k in range(5):
                rr = int(120 + 360 * ((k / 5.0 + fr * 0.01) % 1.0))
                aa = max(0, int(120 * (1 - rr / 480.0)))
                pygame.draw.circle(ps, (180, 30, 130, aa), (bx, by), rr, 2)
            # onde de plaquage au sol autour du héros
            pygame.draw.line(ps, (200, 40, 140, 120), (0, floor_y), (W, floor_y), 2)
            scr.blit(ps, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # ACT III + IV — LA MÉTÉORITE colossale : se forge haut dans le ciel (III),
        # puis Aegis l'ABAT sur le héros traîné au centre (IV).
        if B_STORM <= t < B_SLAM:
            grow = ease(min(1.0, (t - B_STORM) / float(B_RAISE - B_STORM)))
            R = int(46 + 134 * grow)
            if t < B_RAISE:
                my = 150
            else:
                u = ease((t - B_RAISE) / float(B_SLAM - B_RAISE))
                my = int(150 + (floor_y - 150) * (u * u))     # chute accélérée
            # télégraphe d'impact au sol (centre = là où le héros est cloué)
            tgr = R + 24
            tg_a = max(0, min(255, int(130 + 90 * math.sin(fr * 0.25))))
            tgs = pygame.Surface((tgr * 2 + 8, tgr * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(tgs, (255, 40, 60, tg_a), (tgr + 4, tgr + 4), tgr, 4)
            pygame.draw.circle(tgs, (255, 100, 120, 90), (tgr + 4, tgr + 4), int(tgr * 0.62), 2)
            scr.blit(tgs, (cxs - tgr - 4, floor_y - tgr - 4), special_flags=pygame.BLEND_RGBA_ADD)
            # traînée de feu pendant la chute
            if t >= B_RAISE:
                for k in range(1, 8):
                    ty = my - k * 26
                    if ty < -40: break
                    rr = max(2, int(R * (1 - k * 0.12)))
                    ts = pygame.Surface((rr * 2 + 4, rr * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(ts, (255, 120, 50, max(0, 130 - k * 18)), (rr + 2, rr + 2), rr)
                    scr.blit(ts, (cxs - rr - 2, ty - rr - 2), special_flags=pygame.BLEND_RGBA_ADD)
            # corps de la météorite : halo de feu + roche sombre + rim incandescent crénelé
            ms = pygame.Surface((R * 4, R * 4), pygame.SRCALPHA); c = R * 2
            for k in range(5):
                pygame.draw.circle(ms, (255, 110, 40, max(0, 48 - k * 9)), (c, c), int(R * (1.55 - k * 0.16)))
            for k in range(5):
                pygame.draw.circle(ms, (38, 12, 16) if k == 0 else (74, 26, 30), (c, c), int(R * (1.0 - k * 0.16)))
            gl = max(0, min(255, int(175 + 70 * math.sin(fr * 0.3))))
            pygame.draw.circle(ms, (255, 150, 70, gl), (c, c), R, 4)
            for i in range(12):
                a = i * math.tau / 12 + fr * 0.02
                pygame.draw.line(ms, (110, 40, 36),
                                 (c + int(math.cos(a) * R * 0.82), c + int(math.sin(a) * R * 0.82)),
                                 (c + int(math.cos(a) * R * 1.06), c + int(math.sin(a) * R * 1.06)), 3)
            scr.blit(ms, (cxs - c, int(my) - c))
            # rais de charge convergents pendant la forge (acte III)
            if t < B_RAISE:
                for i in range(10):
                    a = i * math.tau / 10 + fr * 0.04
                    rr = R + 70
                    pygame.draw.line(scr, (235, 110, 60),
                                     (cxs + int(math.cos(a) * rr), int(my) + int(math.sin(a) * rr)),
                                     (cxs + int(math.cos(a) * (R + 10)), int(my) + int(math.sin(a) * (R + 10))), 2)

        # Détonation de l'écrasement : ondes de choc au sol.
        if B_SLAM <= t < B_SLAM + 120:
            for k in range(4):
                d = (t - B_SLAM) - k * 11
                if d <= 0: continue
                rr = int(d * 12); aa = max(0, int(220 - d * 2))
                if aa <= 0 or rr <= 0: continue
                col = (255, 255, 255) if k == 0 else ((235, 40, 165) if k % 2 else (120, 12, 150))
                sw = pygame.Surface((rr * 2 + 10, rr * 2 + 10), pygame.SRCALPHA)
                pygame.draw.circle(sw, (*col, aa), (rr + 5, rr + 5), rr, max(2, 9 - k * 2))
                scr.blit(sw, (cxs - rr - 5, floor_y - rr - 5), special_flags=pygame.BLEND_RGBA_ADD)

        # ════════ 2) ZOOM dynamique (keyframes — focus surtout sur le DIEU) ════════
        kf = [
            (0,          bx, by - int(boss.vis * 0.42), 2.20),
            (B_SHATTER,  bx, by - int(boss.vis * 0.42), 2.20),
            (B_ROAR,     bx, by, 1.75),
            (B_PRESSURE, bx, by, 1.62),
            (B_STORM,    cxs, 300, 1.12),     # large + haut : la météorite se forge
            (B_RAISE,    cxs, 300, 1.12),
            (B_SLAM,     cxs, 470, 1.62),     # suit la chute jusqu'à l'impact (héros au centre)
            (B_SLAM + 1, cxs, 480, 1.95),     # coup de zoom sec à l'impact
            (B_VERDICT,  bx, by, 1.45),
            (T,          bx, by, 1.00),       # finit au cadrage gameplay (pas de pop)
        ]
        fx, fy, zoom = bx, by, 1.0
        for i in range(len(kf) - 1):
            t0, fx0, fy0, z0 = kf[i]; t1, fx1, fy1, z1 = kf[i + 1]
            if t0 <= t <= t1:
                e = ease((t - t0) / float(max(1, t1 - t0)))
                fx = fx0 + (fx1 - fx0) * e; fy = fy0 + (fy1 - fy0) * e
                zoom = z0 + (z1 - z0) * e; break

        # Secousse : rumble par acte + montée pendant la chute + pic à l'impact.
        shk = 0.0
        if B_PRESSURE <= t < B_STORM:   shk = 2.5
        elif B_STORM <= t < B_RAISE:    shk = 3.0
        elif B_RAISE <= t < B_SLAM:     shk = 3.0 + 9.0 * ((t - B_RAISE) / float(B_SLAM - B_RAISE))
        ii = t - boss._cx_impact_t
        if 0 <= ii < 18:
            shk = max(shk, boss._cx_impact_amp * (1 - ii / 18.0))
        if shk > 0:
            fx += random.uniform(-shk, shk); fy += random.uniform(-shk, shk)

        if zoom > 1.01:
            sw2 = max(2, int(W / zoom)); sh2 = max(2, int(H / zoom))
            sx = max(0, min(W - sw2, int(fx) - sw2 // 2)); sy = max(0, min(H - sh2, int(fy) - sh2 // 2))
            sub = scr.subsurface(pygame.Rect(sx, sy, sw2, sh2))
            scr.blit(pygame.transform.scale(sub.copy(), (W, H)), (0, 0))

        # ════════ 3) Surcouches plein écran ════════
        bar_max = 74
        if t < 30: bar_h = int(bar_max * t / 30)
        elif t > T - 50: bar_h = int(bar_max * max(0, T - t) / 50)
        else: bar_h = bar_max
        if bar_h > 0:
            for yb in (0, H - bar_h):
                bar = pygame.Surface((W, bar_h), pygame.SRCALPHA); bar.fill((6, 0, 4, 240))
                ly = bar_h - 1 if yb == 0 else 0
                pygame.draw.line(bar, (200, 20, 40), (0, ly), (W, ly), 2)
                scr.blit(bar, (0, yb))
        # vignette rouge — s'intensifie jusqu'à l'écrasement.
        env = (min(1.0, t / 30.0) if t < 30 else (max(0.0, (T - t) / 50.0) if t > T - 50 else 1.0))
        vig = 80 + int(70 * ease(min(1.0, t / float(B_SLAM))))
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.rect(vg, (130, 0, 24, max(0, int(vig * env))), (0, 0, W, H), 120)
        scr.blit(vg, (0, 0))

        def _line(txt, t0, t1, font, y):
            if not (t0 <= t < t1): return
            a = 255
            if t < t0 + 20: a = int(255 * (t - t0) / 20)
            elif t > t1 - 25: a = int(255 * (t1 - t) / 25)
            a = max(0, min(255, a))
            if a <= 0: return
            self._cine_voice_once(("cx", txt), _VOICE_AEGIS_VOID)   # voix grave d'Aegis
            s = font.render(txt, True, (255, 222, 232)); sh = font.render(txt, True, (54, 0, 16))
            s.set_alpha(a); sh.set_alpha(a)
            r = s.get_rect(center=(W // 2, y))
            scr.blit(sh, (r.x + 2, r.y + 2)); scr.blit(s, r)

        # Titre « COURROUX » (claqué à la rupture, se dissipe avant la pression).
        if B_SHATTER - 10 <= t < B_PRESSURE:
            ta = min(255, int((t - (B_SHATTER - 10)) * 12))
            if t > B_PRESSURE - 40: ta = max(0, int(255 * (B_PRESSURE - t) / 40.0))
            if ta > 0:
                nm = self.font_announce.render("COURROUX", True, (255, 50, 50))
                sh3 = self.font_announce.render("COURROUX", True, (40, 0, 0))
                nm.set_alpha(ta); sh3.set_alpha(ta)
                rr = nm.get_rect(center=(W // 2, bar_max // 2 + 6))
                scr.blit(sh3, (rr.x + 3, rr.y + 3)); scr.blit(nm, rr)

        # Répliques de rage / mépris / puissance.
        yb_txt = H - bar_max // 2 - 8
        _line("ASSEZ.", B_ROAR - 6, B_PRESSURE - 10, self.font_big, yb_txt)
        _line("À genoux. Au CENTRE de ma colère.", B_PRESSURE + 40, B_STORM - 20, self.font_med, yb_txt)
        _line("Le ciel va te TOMBER dessus.", B_STORM + 30, B_RAISE - 20, self.font_med, yb_txt)
        _line("VOIS MA PUISSANCE.", B_RAISE + 30, B_SLAM - 10, self.font_big, yb_txt)
        _line("Rampe. Tu n'étais qu'un divertissement.", B_VERDICT + 20, T - 25, self.font_med, yb_txt)

        # White-out de l'écrasement.
        if B_SLAM <= t < B_SLAM + 46:
            fa = max(0, int(255 * (1 - (t - B_SLAM) / 46.0)))
            fs = pygame.Surface((W, H)); fs.fill((255, 255, 255)); fs.set_alpha(fa)
            scr.blit(fs, (0, 0))
        if t < 20:                                      # fondu d'entrée
            fa = int(210 * (1 - t / 20.0))
            fo = pygame.Surface((W, H)); fo.fill((0, 0, 0)); fo.set_alpha(fa)
            scr.blit(fo, (0, 0))

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
                thickness = max(1, int(4 * intensity))
                pygame.draw.line(s, crack_col, origin, tip, thickness)
                # Deuxième ligne décalée pour effet plus épais
                if intensity > 0.6:
                    pygame.draw.line(s, (*Pal.D_ACCENT, min(255, int(alpha * 0.5))),
                                     (origin[0]+2, origin[1]+2), (tip[0]+2, tip[1]+2),
                                     max(1, int(2 * intensity)))
                # petites branches
                mid = ((origin[0] + tip[0]) // 2, (origin[1] + tip[1]) // 2)
                branch = (mid[0] + (tip[1] - origin[1]) // 3,
                          mid[1] - (tip[0] - origin[0]) // 3)
                pygame.draw.line(s, crack_col, mid, branch, 1)
        # Bordure rouge-violet qui pulse
        border_alpha = max(0, min(255, int(100 + 155 * abs(math.sin(self.frame * 0.25)) * intensity)))
        border_w = max(4, int(20 * intensity))
        pygame.draw.rect(s, (*Pal.D_ACCENT, border_alpha), (0, 0, WIDTH, HEIGHT), border_w)
        self.screen.blit(s, (0, 0))
        # Texte d'avertissement
        if intensity > 0.5:
            warn_a = int(200 * ((intensity - 0.5) / 0.5))
            w = self.font_sm.render("FISSURE INSTABLE — retour imminent", True, Pal.D_ACCENT)
            w.set_alpha(warn_a)
            self.screen.blit(w, w.get_rect(midbottom=(WIDTH // 2, HEIGHT - 6)))

    def draw_hud(self):
        # ── Palette dorée partagée ────────────────────────────────────────────
        GOLD        = (215, 160,  40)
        GOLD_BRIGHT = (255, 215,  70)
        GOLD_DARK   = (120,  85,  15)
        GOLD_INNER  = (170, 115,  25)

        # ── Coeur pixel-art (PX=3 → 24×18 px, bien visible) ─────────────────
        PX   = 3
        heart_pattern = [
            "01100110",
            "11111111",
            "11111111",
            "01111110",
            "00111100",
            "00011000",
        ]
        H_W = 8 * PX   # 24
        H_H = 6 * PX   # 18

        # Position : calé sur le bord gauche de l'écran
        hx0  = 8
        hy0  = 8
        frac = max(0.0, self.player.hp / self.player.max_hp)
        heart_col = (220, 50, 15) if frac > 0.35 else \
                    (255, 110,  0) if frac > 0.15 else (200, 20, 20)
        if frac <= 0:
            heart_col = (50, 10, 10)
        light_col = tuple(min(255, c + 80) for c in heart_col)

        # Ombre du cadran coeur
        pygame.draw.rect(self.screen, (8, 4, 0),
                         (hx0 - 2, hy0 - 2, H_W + 8, H_H + 8), border_radius=5)
        # Fond intérieur sombre
        pygame.draw.rect(self.screen, (30, 5, 5),
                         (hx0, hy0, H_W, H_H))
        # Pixels du coeur
        for ri, row in enumerate(heart_pattern):
            for ci, px_val in enumerate(row):
                if px_val == '1':
                    c_px = light_col if ri == 0 else heart_col
                    pygame.draw.rect(self.screen, c_px,
                                     (hx0 + ci * PX, hy0 + ri * PX, PX, PX))
        # Cadran doré autour du coeur
        pygame.draw.rect(self.screen, GOLD_DARK,
                         (hx0 - 3, hy0 - 3, H_W + 6, H_H + 6), 3, border_radius=5)
        pygame.draw.rect(self.screen, GOLD,
                         (hx0 - 2, hy0 - 2, H_W + 4, H_H + 4), 2, border_radius=4)
        pygame.draw.line(self.screen, GOLD_BRIGHT,
                         (hx0, hy0 - 2), (hx0 + H_W - 1, hy0 - 2))
        # Clous aux coins
        for cx2, cy2 in [(hx0-3, hy0-3), (hx0+H_W-1, hy0-3),
                         (hx0-3, hy0+H_H-1), (hx0+H_W-1, hy0+H_H-1)]:
            pygame.draw.rect(self.screen, GOLD_BRIGHT, (cx2, cy2, 4, 4))
            pygame.draw.rect(self.screen, GOLD_INNER,  (cx2+1, cy2+1, 2, 2))

        # ── Barre HP (démarre juste après le coeur) ───────────────────────────
        BAR_X = hx0 + H_W + 10   # 8 + 24 + 10 = 42 → toujours à l'écran
        BAR_Y = hy0 + (H_H - 14) // 2
        BAR_W = 180
        BAR_H = 14
        fill_sw = int(BAR_W * frac)

        # Ombre portée
        pygame.draw.rect(self.screen, (10, 5, 0),
                         (BAR_X + 2, BAR_Y + 2, BAR_W + 6, BAR_H + 6), border_radius=3)
        # Fond sombre
        pygame.draw.rect(self.screen, (38, 10, 10),
                         (BAR_X, BAR_Y, BAR_W, BAR_H), border_radius=3)
        # Fill
        if fill_sw > 0:
            pygame.draw.rect(self.screen, heart_col,
                             (BAR_X + 1, BAR_Y + 1, max(1, fill_sw - 1), BAR_H - 2),
                             border_radius=2)
            pygame.draw.rect(self.screen,
                             tuple(min(255, c + 60) for c in heart_col),
                             (BAR_X + 1, BAR_Y + 1, max(1, fill_sw - 1), 3),
                             border_radius=2)
        # Cadran doré barre
        pygame.draw.rect(self.screen, GOLD_DARK,
                         (BAR_X - 3, BAR_Y - 3, BAR_W + 6, BAR_H + 6), 3, border_radius=4)
        pygame.draw.rect(self.screen, GOLD,
                         (BAR_X - 2, BAR_Y - 2, BAR_W + 4, BAR_H + 4), 2, border_radius=4)
        pygame.draw.line(self.screen, GOLD_BRIGHT,
                         (BAR_X, BAR_Y - 2), (BAR_X + BAR_W - 1, BAR_Y - 2))
        for cx2, cy2 in [(BAR_X - 3, BAR_Y - 3),
                         (BAR_X + BAR_W - 1, BAR_Y - 3),
                         (BAR_X - 3, BAR_Y + BAR_H - 1),
                         (BAR_X + BAR_W - 1, BAR_Y + BAR_H - 1)]:
            pygame.draw.rect(self.screen, GOLD_BRIGHT, (cx2, cy2, 4, 4))
            pygame.draw.rect(self.screen, GOLD_INNER,  (cx2 + 1, cy2 + 1, 2, 2))

        # Bouclier
        if self.player.shield > 0:
            sy2 = BAR_Y + BAR_H + 6
            shield_frac = min(1.0, self.player.shield / 10)
            pygame.draw.rect(self.screen, (20, 60, 30),
                             (BAR_X, sy2, BAR_W, 6), border_radius=3)
            pygame.draw.rect(self.screen, (60, 220, 100),
                             (BAR_X, sy2, int(BAR_W * shield_frac), 6), border_radius=3)
            pygame.draw.rect(self.screen, (120, 255, 150),
                             (BAR_X, sy2, BAR_W, 6), 1, border_radius=3)
            sh_lbl = self.font_sm.render(f"BOUCLIER  {self.player.shield}",
                                         True, (120, 255, 150))
            self.screen.blit(sh_lbl, (BAR_X + 4, sy2))

        lbl = "REALITE" if self.player.dimension == DIM_REAL else "REVE BRISE"
        col = pal_accent(self.player.dimension)
        d_surf = self.font_sm.render(lbl, True, col)
        self.screen.blit(d_surf, (BAR_X, BAR_Y + BAR_H + 5))

        # ── Barre fissure (sous barre HP, même largeur) ───────────────────────
        swap_y = BAR_Y + BAR_H + (14 if self.player.shield > 0 else 4)
        ready = self.player.swap_cooldown <= 0
        swap_frac = 1.0 if ready else 1.0 - self.player.swap_cooldown / SWAP_COOLDOWN
        swap_col = (100, 220, 255) if ready else (60, 120, 160)
        pygame.draw.rect(self.screen, (15, 30, 40),
                         (BAR_X, swap_y, BAR_W, 6), border_radius=3)
        pygame.draw.rect(self.screen, swap_col,
                         (BAR_X, swap_y, int(BAR_W * swap_frac), 6), border_radius=3)
        if ready:
            pygame.draw.rect(self.screen, (180, 255, 255),
                             (BAR_X, swap_y, BAR_W, 6), 1, border_radius=3)
        swap_lbl = self.font_sm.render("FISSURE", True, swap_col)
        self.screen.blit(swap_lbl, (BAR_X + BAR_W + 6, swap_y - 2))


        # ── Chrono rêve (haut à droite quand dimension == DIM_DREAM) ─────────
        if self.player.dimension == DIM_DREAM:
            remaining = max(0, DREAM_MAX_STAY - self.player.dream_stay_t)
            secs = remaining // 60
            frames = remaining % 60
            chrono_col = (200, 160, 255) if remaining > DREAM_MAX_STAY * 0.35 else (255, 80, 120)
            chrono_str = f"{secs}:{frames:02d}"
            c_surf = self.font_med.render(chrono_str, True, chrono_col)
            # Fond semi-transparent
            pad = 6
            cr = c_surf.get_rect(topright=(WIDTH - 12, 8))
            bg_s = pygame.Surface((cr.w + pad * 2, cr.h + pad * 2), pygame.SRCALPHA)
            bg_s.fill((0, 0, 0, 140))
            pygame.draw.rect(bg_s, (*chrono_col, 100), (0, 0, cr.w + pad * 2, cr.h + pad * 2), 1, border_radius=4)
            self.screen.blit(bg_s, (cr.x - pad, cr.y - pad))
            self.screen.blit(c_surf, cr)

    def draw_boss_ui(self):
        if not self.boss: return

        # ══════════════════════════════════════════════════════════════════════
        # BARRE DE VIE DU BOSS — procédurale, longue et fine
        # Dimensions : 820px × 14px, centrée, à y=30 du haut de l'écran
        # ══════════════════════════════════════════════════════════════════════
        BAR_W    = 820    # largeur totale (cadran inclus)
        BAR_H    = 18     # hauteur totale
        BAR_Y    = 46     # position verticale du haut de la barre
        BAR_X    = WIDTH // 2 - BAR_W // 2
        PAD      = 3      # espace intérieur entre bordure et fill
        FILL_W   = BAR_W - PAD * 2
        FILL_H   = BAR_H - PAD * 2
        FILL_X   = BAR_X + PAD
        FILL_Y   = BAR_Y + PAD

        frac = self.boss.display_bar_fraction()

        # ── Couleur du fill selon la phase ───────────────────────────────────
        if self.boss.last_resort_active:
            pulse     = abs(math.sin(self.frame * 0.18))
            phase_col = (int(220 + 35 * pulse), int(20 * (1 - pulse)), 15)
        elif isinstance(self.boss, AegisBoss):
            # Palette propre à Aegis : se corrompt phase après phase (or → magenta → vide)
            phase_col = {
                1: _AEGIS_COL_LIGHT, 2: _AEGIS_COL_LIGHT, 3: _AEGIS_COL_MIXED,
                4: _AEGIS_COL_DARK,  5: _AEGIS_COL_DARK2,  6: (200, 30, 150),
                7: _AEGIS_COL_VOID,
            }.get(self.boss.phase, _AEGIS_COL_DARK)
        elif self.boss.phase == 5:
            phase_col = (210, 20, 55) if self.boss.final_form else (175, 45, 95)
        elif self.boss.phase == 4: phase_col = (255, 100, 180)
        elif self.boss.phase == 3: phase_col = (110, 110, 205)
        else:                       phase_col = (210, 35, 18)

        # ── 1. Fond sombre de la barre ────────────────────────────────────────
        pygame.draw.rect(self.screen, (8, 4, 14),
                         (BAR_X, BAR_Y, BAR_W, BAR_H), border_radius=3)

        # ── 2. Fill (centré → vide depuis les deux extrémités) ────────────────
        fill_sw = max(0, int(FILL_W * frac))
        if fill_sw > 0:
            _side_empty = (FILL_W - fill_sw) // 2
            fx = FILL_X + _side_empty
            # Remplissage principal
            pygame.draw.rect(self.screen, phase_col,
                             (fx, FILL_Y, fill_sw, FILL_H), border_radius=2)
            # Reflet lumineux (ligne fine en haut du fill)
            hi_col = tuple(min(255, c + 65) for c in phase_col)
            pygame.draw.rect(self.screen, hi_col,
                             (fx, FILL_Y, fill_sw, max(1, FILL_H // 3)), border_radius=1)

        # ── 3. Cadran doré par-dessus (bordure + coins) ───────────────────────
        # Bordure principale
        pygame.draw.rect(self.screen, (180, 145, 40),
                         (BAR_X, BAR_Y, BAR_W, BAR_H), 1, border_radius=3)
        # Ligne intérieure plus sombre
        pygame.draw.rect(self.screen, (100, 80, 20),
                         (BAR_X + 1, BAR_Y + 1, BAR_W - 2, BAR_H - 2), 1, border_radius=2)
        # Petits boulons aux 4 coins
        for bx, by in ((BAR_X + 3, BAR_Y + 3), (BAR_X + BAR_W - 5, BAR_Y + 3),
                       (BAR_X + 3, BAR_Y + BAR_H - 5), (BAR_X + BAR_W - 5, BAR_Y + BAR_H - 5)):
            pygame.draw.rect(self.screen, (210, 175, 55), (bx, by, 2, 2))

        # ── Textes ────────────────────────────────────────────────────────────
        bar_screen_y = BAR_Y
        below_y = BAR_Y + BAR_H + 3

        _bname = getattr(self.boss, 'display_name', 'LA LUNE')
        _bcount = getattr(self.boss, 'phase_count', 5)
        if isinstance(self.boss, AegisBoss):
            # 2 phases VISIBLES : I (avant COURROUX) / II (après). Le niveau
            # interne (forme + attaques) morphe en continu avec les PV, sans bannière.
            _act = 1 if self.boss.phase <= 3 else 2
            name = self.font_sm.render(f"{_bname}  —  Phase {_act} / 2", True, Pal.UI)
        else:
            name = self.font_sm.render(f"{_bname}  —  Phase {self.boss.phase} / {_bcount}", True, Pal.UI)
        self.screen.blit(name, name.get_rect(midbottom=(WIDTH // 2, bar_screen_y - 2)))

        # Phase 2 : dimension vulnérable (Lune uniquement)
        if isinstance(self.boss, MoonBoss) and self.boss.phase == 2 and self.boss.state == "fighting":
            dlbl = "Vulnerable : " + ("REALITE" if self.boss.dim == DIM_REAL else "REVE BRISE")
            dc = pal_accent(self.boss.dim)
            s = self.font_sm.render(dlbl, True, dc)
            self.screen.blit(s, s.get_rect(midtop=(WIDTH // 2, below_y)))

        # Derniers Recours
        if self.boss.last_resort_active:
            t     = self.boss.last_resort_t
            pulse = abs(math.sin(self.frame * 0.18))
            w_surf = self.font_sm.render("!! DERNIERS RECOURS !!",
                                         True, (255, int(80 + 80 * pulse), 20))
            self.screen.blit(w_surf, w_surf.get_rect(midtop=(WIDTH // 2, below_y)))
            if t < 185:
                phase_names = {0: "CRISE", 50: "FUITE", 110: "VIDE", 155: "RETOUR"}
                phase_str = "CRISE"
                for threshold, pname in sorted(phase_names.items()):
                    if t >= threshold:
                        phase_str = pname
                ps = self.font_sm.render(phase_str, True, (255, 150, 80))
                self.screen.blit(ps, ps.get_rect(midtop=(WIDTH // 2, below_y + 18)))

        # Post-DR
        if self.boss and self.boss.post_dr and not self.boss.last_resort_active:
            def_s = self.font_sm.render("DEFENSE ACCRUE  fleches -50%", True, (255, 100, 80))
            self.screen.blit(def_s, def_s.get_rect(midtop=(WIDTH // 2, below_y)))

        # God mode
        if self.god_mode:
            gm_s = self.font_sm.render("GOD MODE", True, (100, 255, 120))
            self.screen.blit(gm_s, gm_s.get_rect(topright=(WIDTH - 8, 6)))

    def draw_skill_bar(self):
        """Barre de compétences bas-centre (style Soulslike Abyss)."""
        if not self.player: return

        # ── Définition des slots ──────────────────────────────────────────────
        skills = [
            {
                'key': 'Clic',
                'name': 'Attaque',
                'cd': self.player.bow_cd,
                'cd_max': BOW_COOLDOWN,
                'color': (220, 160, 60),
                'icon': 'sword',
                'active': False,
            },
            {
                'key': 'A / Maj',
                'name': 'Dash',
                'cd': self.player.dash_cooldown,
                'cd_max': DASH_COOLDOWN,
                'color': (80, 200, 220),
                'icon': 'dash',
                'active': self.player.dash_timer > 0,
            },
        ]
        if self.shield_unlocked:
            skills.append({
                'key': '1',
                'name': 'Bouclier',
                'cd': self.ability_shield_cd,
                'cd_max': self.SHIELD_CD,
                'color': (60, 140, 255),
                'icon': 'shield',
                'active': self.ability_shield_t > 0,
            })

        SLOT = 72
        GAP  = 16
        total_w = len(skills) * SLOT + (len(skills) - 1) * GAP
        # Panneau fond global
        PAD_X, PAD_Y = 18, 10
        panel_w = total_w + PAD_X * 2
        panel_h = SLOT + PAD_Y * 2 + 20  # +20 pour le nom en bas
        px = WIDTH // 2 - panel_w // 2
        py = HEIGHT - panel_h - 8
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((8, 5, 18, 210))
        # Bordure dorée fine
        pygame.draw.rect(panel, (140, 110, 40), (0, 0, panel_w, panel_h), 1, border_radius=6)
        pygame.draw.rect(panel, (60, 45, 15), (1, 1, panel_w - 2, panel_h - 2), 1, border_radius=5)
        self.screen.blit(panel, (px, py))

        sx0 = px + PAD_X
        sy0 = py + PAD_Y

        for i, sk in enumerate(skills):
            sx = sx0 + i * (SLOT + GAP)
            cx = sx + SLOT // 2
            cy = sy0 + SLOT // 2
            col = sk['color']
            ready = sk['cd'] <= 0

            # ── Glow actif (derrière le slot) ─────────────────────────────────
            if sk['active']:
                pulse = abs(math.sin(self.frame * 0.15))
                glow  = pygame.Surface((SLOT + 12, SLOT + 12), pygame.SRCALPHA)
                pygame.draw.rect(glow,
                                 (*col, int(80 + 90 * pulse)),
                                 (0, 0, SLOT + 12, SLOT + 12), 4, border_radius=8)
                self.screen.blit(glow, (sx - 6, sy0 - 6))

            # ── Fond slot (texture Soulslike ou fallback) ─────────────────────
            if self._ui_slot:
                slot_scaled = pygame.transform.scale(self._ui_slot, (SLOT, SLOT))
                self.screen.blit(slot_scaled, (sx, sy0))
            else:
                pygame.draw.rect(self.screen, (22, 15, 35),
                                 (sx, sy0, SLOT, SLOT), border_radius=5)
            # Bordure slot colorée (dorée si prêt, grise si cooldown)
            border_col = (180, 140, 50) if ready else (60, 50, 80)
            pygame.draw.rect(self.screen, border_col,
                             (sx, sy0, SLOT, SLOT), 2, border_radius=5)

            # ── Icône procédurale ─────────────────────────────────────────────
            icon_col = col if ready else tuple(c // 2 for c in col)
            if sk['icon'] == 'sword':
                pygame.draw.line(self.screen, icon_col,
                                 (cx - 15, cy + 15), (cx + 15, cy - 15), 4)
                pygame.draw.line(self.screen, icon_col,
                                 (cx - 10, cy - 4), (cx - 1, cy + 5), 3)
                pygame.draw.circle(self.screen, icon_col, (cx - 15, cy + 15), 4)
            elif sk['icon'] == 'dash':
                pts = [(cx + 17, cy),
                       (cx + 4,  cy - 10),
                       (cx + 4,  cy - 5),
                       (cx - 17, cy - 5),
                       (cx - 17, cy + 5),
                       (cx + 4,  cy + 5),
                       (cx + 4,  cy + 10)]
                pygame.draw.polygon(self.screen, icon_col, pts)
            elif sk['icon'] == 'shield':
                pts = [(cx, cy - 17),
                       (cx + 14, cy - 8),
                       (cx + 14, cy + 6),
                       (cx,      cy + 17),
                       (cx - 14, cy + 6),
                       (cx - 14, cy - 8)]
                pygame.draw.polygon(self.screen, icon_col, pts)
                pygame.draw.polygon(self.screen, (10, 5, 20), pts, 2)
                pygame.draw.line(self.screen, tuple(min(255, c + 80) for c in icon_col),
                                 (cx, cy - 10), (cx, cy + 8), 2)
                pygame.draw.line(self.screen, tuple(min(255, c + 80) for c in icon_col),
                                 (cx - 8, cy), (cx + 8, cy), 2)

            # ── Overlay cooldown (de haut vers le bas) ────────────────────────
            if sk['cd'] > 0 and sk['cd_max'] > 0:
                frac    = min(1.0, sk['cd'] / sk['cd_max'])
                ov_h    = max(1, int(SLOT * frac))
                ov_surf = pygame.Surface((SLOT, ov_h), pygame.SRCALPHA)
                ov_surf.fill((0, 0, 0, 190))
                self.screen.blit(ov_surf, (sx, sy0))
                # Barre de progression fine en bas du slot
                bar_frac  = 1.0 - frac
                bar_w_px  = max(1, int(SLOT * bar_frac))
                pygame.draw.rect(self.screen, (30, 20, 50),
                                 (sx, sy0 + SLOT - 5, SLOT, 4), border_radius=2)
                pygame.draw.rect(self.screen, col,
                                 (sx, sy0 + SLOT - 5, bar_w_px, 4), border_radius=2)
                # Compteur secondes centré (si > 1s)
                if sk['cd'] > 60:
                    secs = math.ceil(sk['cd'] / 60)
                    ct = self.font_sm.render(f"{secs}s", True, (230, 220, 255))
                    self.screen.blit(ct, ct.get_rect(center=(cx, cy)))

            # ── Nom + touche en bas du slot ───────────────────────────────────
            name_col = (200, 180, 255) if ready else (100, 90, 130)
            name_s = self.font_sm.render(sk['name'], True, name_col)
            key_s  = self.font_sm.render(f"[{sk['key']}]", True, (120, 110, 160))
            self.screen.blit(name_s, name_s.get_rect(midtop=(cx, sy0 + SLOT + 5)))
            self.screen.blit(key_s,  key_s.get_rect(midtop=(cx, sy0 + SLOT + 5 + name_s.get_height())))

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

    def draw_screen_flash(self):
        if self.flash_t <= 0:
            return
        t = self.flash_t / max(1, self.flash_max)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((*self.flash_col, int(235 * t)))
        self.screen.blit(veil, (0, 0))

    def draw_subtitle(self):
        """Sous-titre de forme (« Le masque se fissure… ») pendant les transitions."""
        if self.subtitle_t <= 0 or not self.subtitle_text:
            return
        t = self.subtitle_t / max(1, self.subtitle_max)
        if t > 0.8:
            fade = (1.0 - t) / 0.2
        elif t < 0.25:
            fade = t / 0.25
        else:
            fade = 1.0
        fade = max(0.0, min(1.0, fade))
        surf = self.font_sm.render(self.subtitle_text, True, (255, 210, 240))
        surf.set_alpha(int(255 * fade))
        self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 78)))

    def draw_attack_callout(self):
        """Nom de l'attaque spéciale d'Aegis : claque en haut de l'écran pour
        qu'on VOIE chaque attaque divine — punch-in, maintien, fondu."""
        if self.callout_t <= 0 or not self.callout_text:
            return
        t = self.callout_t / max(1, self.callout_max)
        if t > 0.86:                      # punch-in : gros → normal + fade in
            fade = (1.0 - t) / 0.14
            scl  = 1.0 + (t - 0.86) / 0.14 * 0.4
        elif t < 0.32:                    # fondu sortant
            fade = t / 0.32
            scl  = 1.0
        else:
            fade = 1.0
            scl  = 1.0
        fade = max(0.0, min(1.0, fade))
        col = self.boss._form_color() if isinstance(self.boss, AegisBoss) \
            else _AEGIS_COL_DARK2
        cx, cy = WIDTH // 2, 152
        txt = self.font_med.render(self.callout_text, True, (255, 244, 252))
        if scl != 1.0:
            txt = pygame.transform.rotozoom(txt, 0, scl)
        txt.set_alpha(int(255 * fade))
        tw, th = txt.get_size()
        pad_x, pad_y = 36, 9
        band = pygame.Surface((tw + pad_x * 2, th + pad_y * 2), pygame.SRCALPHA)
        band.fill((12, 4, 20, int(165 * fade)))
        pygame.draw.rect(band, (*col, int(225 * fade)), band.get_rect(),
                         width=2, border_radius=3)
        brect = band.get_rect(center=(cx, cy))
        # chevrons latéraux (dessinés sur le bandeau alpha pour fondre proprement)
        for sgn in (-1, 1):
            ex = pad_x // 2 if sgn < 0 else band.get_width() - pad_x // 2
            tip = ex + sgn * 7
            pygame.draw.lines(band, (*col, int(225 * fade)), False,
                              [(ex, pad_y), (tip, band.get_height() // 2),
                               (ex, band.get_height() - pad_y)], 2)
        self.screen.blit(band, brect)
        self.screen.blit(txt, txt.get_rect(center=(cx, cy)))
        # tag « ATTAQUE DIVINE »
        tag = self.font_sm.render("— ATTAQUE DIVINE —", True, col)
        tag.set_alpha(int(170 * fade))
        self.screen.blit(tag, tag.get_rect(center=(cx, cy + th // 2 + pad_y + 13)))

    def draw_god_dialog(self):
        pw, ph = 340, 180
        px = (WIDTH - pw) // 2
        py = (HEIGHT - ph) // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 0, 25, 220))
        pygame.draw.rect(panel, (160, 60, 220), (0, 0, pw, ph), 2)
        self.screen.blit(panel, (px, py))
        # Title
        title = self.font_med.render("MOT DE PASSE", True, (200, 140, 255))
        self.screen.blit(title, title.get_rect(midtop=(WIDTH // 2, py + 18)))
        # Masked input
        dots = "●" * len(self.god_input) + "▌" if len(self.god_input) < 4 else "●" * 4
        inp_surf = self.font_big.render(dots, True, (240, 200, 255))
        self.screen.blit(inp_surf, inp_surf.get_rect(center=(WIDTH // 2, py + 90)))
        # Status
        if self.god_mode:
            status = self.font_sm.render("GOD MODE ACTIF", True, (100, 255, 120))
        else:
            status = self.font_sm.render("ENTRÉE → valider   ÉCHAP → annuler", True, (130, 100, 180))
        self.screen.blit(status, status.get_rect(midbottom=(WIDTH // 2, py + ph - 14)))

    def _draw_boss_dialog(self, lines, t, max_t=120, angry=False, divine=False):
        """Bulle de dialogue animée. Les lettres apparaissent une à une."""
        if t <= 0 or t >= max_t:
            return
        fade_in = min(1.0, t / 20.0)
        fade_out = max(0.0, 1.0 - max(0.0, t - (max_t - 20)) / 20.0)
        alpha = max(0, min(255, int(255 * fade_in * fade_out)))
        if alpha <= 0:
            return

        pw, ph = 540, 110
        px = (WIDTH - pw) // 2
        py = HEIGHT - ph - 50

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        if divine:
            panel.fill((240, 240, 200, max(0, min(255, int(210 * alpha / 255)))))
            border_col = (255, 220, 60)
            text_col = (80, 50, 0)
        elif angry:
            panel.fill((30, 0, 10, max(0, min(255, int(220 * alpha / 255)))))
            border_col = (200, 30, 60)
            text_col = (255, 160, 160)
        else:
            panel.fill((10, 0, 25, max(0, min(255, int(220 * alpha / 255)))))
            border_col = (130, 50, 180)
            text_col = (220, 190, 255)

        pygame.draw.rect(panel, border_col, (0, 0, pw, ph), 2)
        self.screen.blit(panel, (px, py))

        # Lettres apparaissent progressivement
        chars_visible = int(t * 0.75)
        # Blip de « voix » : Aegis (divine) sinon la Lune (Derniers Recours).
        _total = sum(len(l) for l in lines)
        if (chars_visible > int((t - 1) * 0.75)
                and 0 < chars_visible <= _total and chars_visible % 2 == 0):
            self._play_text_blip(_VOICE_AEGIS if divine else _VOICE_MOON)
        y_off = py + 16
        shown_so_far = 0
        for line in lines:
            remaining = max(0, chars_visible - shown_so_far)
            txt = line[:remaining]
            shown_so_far += len(line) + 2
            if txt:
                dx = random.randint(-2, 2) if angry else 0
                dy = random.randint(-1, 1) if angry else 0
                surf = self.font_med.render(txt, True, text_col)
                surf.set_alpha(alpha)
                self.screen.blit(surf, (px + 16 + dx, y_off + dy))
            y_off += 36

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

        # Bouton DÉMARRER cliquable
        btn_w, btn_h = 260, 48
        btn_x = WIDTH // 2 - btn_w // 2
        btn_y = HEIGHT // 2 + 20
        self.start_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        mx, my = pygame.mouse.get_pos()
        hovered = self.start_btn_rect.collidepoint(mx, my)
        btn_bg   = (80, 50, 160) if hovered else (40, 24, 90)
        btn_border = (200, 160, 255) if hovered else (120, 80, 200)
        btn_text_col = (255, 255, 255) if hovered else (210, 190, 255)
        pygame.draw.rect(self.screen, btn_bg, self.start_btn_rect, border_radius=10)
        pygame.draw.rect(self.screen, btn_border, self.start_btn_rect, 2, border_radius=10)
        if hovered:
            glow = pygame.Surface((btn_w + 20, btn_h + 20), pygame.SRCALPHA)
            pygame.draw.rect(glow, (120, 80, 255, 40), (0, 0, btn_w + 20, btn_h + 20), border_radius=14)
            self.screen.blit(glow, (btn_x - 10, btn_y - 10))
        lbl = self.font_med.render("DÉMARRER", True, btn_text_col)
        self.screen.blit(lbl, lbl.get_rect(center=self.start_btn_rect.center))

        # Bouton secret PHASE 5 (visible seulement si déverrouillé)
        if self.phase5_unlocked:
            p5_w, p5_h = 260, 48
            p5_x = WIDTH // 2 - p5_w // 2
            p5_y = btn_y + btn_h + 16
            self.start_phase5_btn_rect = pygame.Rect(p5_x, p5_y, p5_w, p5_h)
            p5_hovered = self.start_phase5_btn_rect.collidepoint(mx, my)
            p5_bg     = (120, 10, 50) if p5_hovered else (60, 5, 28)
            p5_border  = (255, 100, 180) if p5_hovered else (180, 50, 100)
            p5_text_col = (255, 200, 230) if p5_hovered else (220, 150, 190)
            pygame.draw.rect(self.screen, p5_bg, self.start_phase5_btn_rect, border_radius=10)
            pygame.draw.rect(self.screen, p5_border, self.start_phase5_btn_rect, 2, border_radius=10)
            if p5_hovered:
                glow5 = pygame.Surface((p5_w + 20, p5_h + 20), pygame.SRCALPHA)
                pygame.draw.rect(glow5, (220, 60, 130, 45), (0, 0, p5_w + 20, p5_h + 20), border_radius=14)
                self.screen.blit(glow5, (p5_x - 10, p5_y - 10))
            p5_lbl = self.font_med.render("⚡ PHASE 5", True, p5_text_col)
            self.screen.blit(p5_lbl, p5_lbl.get_rect(center=self.start_phase5_btn_rect.center))

        # Bouton secret AEGIS (visible seulement si déverrouillé via P×20)
        if self.aegis_unlocked:
            ag_w, ag_h = 260, 48
            ag_x = WIDTH // 2 - ag_w // 2
            ag_y = (self.start_phase5_btn_rect.bottom if self.phase5_unlocked else btn_y + btn_h) + 16
            self.start_aegis_btn_rect = pygame.Rect(ag_x, ag_y, ag_w, ag_h)
            ag_hovered = self.start_aegis_btn_rect.collidepoint(mx, my)
            ag_pulse = 0.6 + 0.4 * math.sin(self.title_pulse_t * 0.08)
            ag_bg     = (40, 10, 70) if ag_hovered else (22, 6, 40)
            ag_border  = (190, 90, 255) if ag_hovered else (120, 50, 190)
            ag_text_col = (235, 200, 255) if ag_hovered else (190, 150, 230)
            pygame.draw.rect(self.screen, ag_bg, self.start_aegis_btn_rect, border_radius=10)
            pygame.draw.rect(self.screen, ag_border, self.start_aegis_btn_rect, 2, border_radius=10)
            glowA = pygame.Surface((ag_w + 24, ag_h + 24), pygame.SRCALPHA)
            pygame.draw.rect(glowA, (150, 60, 230, int(50 * ag_pulse)),
                             (0, 0, ag_w + 24, ag_h + 24), border_radius=16)
            self.screen.blit(glowA, (ag_x - 12, ag_y - 12))
            ag_lbl = self.font_med.render("✦ AEGIS", True, ag_text_col)
            self.screen.blit(ag_lbl, ag_lbl.get_rect(center=self.start_aegis_btn_rect.center))

        # Hint contrôles en bas
        hint_col = (180, 160, 220)
        hint = self.font_sm.render("[C]  Contrôles", True, hint_col)
        self.screen.blit(hint, hint.get_rect(midbottom=(WIDTH // 2, HEIGHT - 24)))

        # Popup contrôles
        if self.show_controls_popup:
            ctrl_lines = [
                ("ESPACE",        "Saut  /  Double saut"),
                ("ESPACE x3",     "3x en l'air = changer de dimension (swap)"),
                ("A  ou  MAJ",    "Dash  —  traverse les projectiles roses = PARRY"),
                ("Clic gauche",   "Tirer une fleche  (maintenir = charge)"),
                ("TAB",           "Ouvrir les parametres de volume"),
                ("F  ou  F11",    "Plein ecran"),
                ("ECHAP",         "Retour au titre / quitter"),
                ("", ""),
                ("COULEURS TELEGRAPHS", ""),
                ("Bleu",          "Attaque dans le monde REEL"),
                ("Rose",          "Attaque dans le monde REVE"),
                ("Orange",        "Attaque INEVITABLE (touche les 2 mondes)"),
            ]
            pad = 24
            lh = 28
            max_visible = 7
            panel_w = 720
            panel_h = pad * 2 + max_visible * lh + 10
            panel_x = WIDTH // 2 - panel_w // 2
            panel_y = HEIGHT // 2 + 60
            max_scroll = max(0, len(ctrl_lines) - max_visible)
            self.controls_scroll = max(0, min(self.controls_scroll, max_scroll))
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((12, 6, 28, 215))
            self.screen.blit(panel, (panel_x, panel_y))
            pygame.draw.rect(self.screen, (100, 60, 200),
                             (panel_x, panel_y, panel_w, panel_h), 2, border_radius=8)
            clip_rect = pygame.Rect(panel_x + 2, panel_y + 2, panel_w - 4, panel_h - 4)
            old_clip = self.screen.get_clip()
            self.screen.set_clip(clip_rect)
            visible = ctrl_lines[self.controls_scroll: self.controls_scroll + max_visible]
            for i, (key, action) in enumerate(visible):
                ky = panel_y + pad + i * lh
                if key == "COULEURS TELEGRAPHS":
                    s = self.font_sm.render("--- COULEURS DES TELEGRAPHS ---", True, (180, 150, 255))
                    self.screen.blit(s, (panel_x + 18, ky))
                    continue
                if key == "":
                    continue
                if key == "Bleu":   col_key = (80, 160, 255)
                elif key == "Rose": col_key = (255, 100, 200)
                elif key == "Orange": col_key = (255, 185, 45)
                else: col_key = (200, 180, 255)
                k_surf = self.font_sm.render(key, True, col_key)
                a_surf = self.font_sm.render(action, True, (160, 150, 200))
                self.screen.blit(k_surf, (panel_x + 18, ky))
                self.screen.blit(a_surf, (panel_x + 200, ky))
            self.screen.set_clip(old_clip)
            if max_scroll > 0:
                hint = self.font_sm.render(f"Molette pour defiler  ({self.controls_scroll+1}/{max_scroll+1})", True, (120, 100, 160))
                self.screen.blit(hint, (panel_x + panel_w // 2 - hint.get_width() // 2,
                                        panel_y + panel_h - 20))

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
        self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
        sc = self.font_med.render(f"Score : {self.player.score}", True, Pal.UI_DARK)
        self.screen.blit(sc, sc.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        if self.victory_timer > 0:
            secs_left = max(0, (300 - self.victory_timer) // 60 + 1)
            sub = self.font_med.render(f"Retour au sanctuaire dans {secs_left}…   R — maintenant", True, Pal.UI_DARK)
        else:
            sub = self.font_med.render("R — retour au hub", True, Pal.UI_DARK)
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60)))


    def _draw_divine_sword(self, cx, cy, progress):
        """Épée divine procédurale — pointe vers le bas, descend du ciel.
        cx, cy = position de la POINTE (extrémité basse, dirigée vers le boss).
        """
        if progress <= 0:
            return
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        alpha  = max(0, min(255, int(255 * progress)))
        scale  = 0.45 + 0.55 * progress

        # Dimensions
        blade_len = int(195 * scale)
        blade_w   = int(30 * scale)
        cg_w      = int(88 * scale)    # garde / crossguard
        cg_h      = int(18 * scale)
        grip_len  = int(62 * scale)
        grip_w    = int(15 * scale)
        pommel_r  = int(19 * scale)

        # Positions clés (tout part de cy = pointe, monte vers le haut)
        tip_y      = cy
        cg_y       = cy - blade_len               # pied de la garde
        grip_top   = cg_y - cg_h - grip_len       # sommet de la poignée
        pommel_cy  = grip_top - pommel_r           # centre du pommeau

        # ── PILIER DE LUMIÈRE (du haut de l'écran jusqu'à la pointe) ─────────
        pillar_w = max(6, int(72 * progress))
        core_w   = max(3, int(18 * progress))
        for by_px in range(0, cy + 1, 8):
            frac = 1.0 - by_px / max(1, cy)
            ba   = max(0, int(alpha * 0.32 * frac))
            pygame.draw.rect(s, (190, 215, 255, ba),
                             (cx - pillar_w // 2, by_px, pillar_w, 8))
        for by_px in range(0, cy + 1, 6):
            frac = 1.0 - by_px / max(1, cy)
            ba   = max(0, int(alpha * 0.60 * frac))
            pygame.draw.rect(s, (255, 255, 255, ba),
                             (cx - core_w // 2, by_px, core_w, 6))

        # ── AURA BLEUE-BLANCHE autour de la lame ──────────────────────────────
        for extra, aa in [(44, 28), (28, 50), (14, 75)]:
            aw = blade_w // 2 + int(extra * scale)
            apts = [
                (cx - aw, cg_y),
                (cx + aw, cg_y),
                (cx + max(2, int(3 * scale)), tip_y),
                (cx - max(2, int(3 * scale)), tip_y),
            ]
            pygame.draw.polygon(s, (175, 210, 255, max(0, int(aa * progress))), apts)

        # ── LAME ──────────────────────────────────────────────────────────────
        # Silhouette principale (argent froid)
        blade_pts = [
            (cx - blade_w // 2, cg_y),
            (cx + blade_w // 2, cg_y),
            (cx + max(1, int(2 * scale)), tip_y - int(6 * scale)),
            (cx,                           tip_y),
            (cx - max(1, int(2 * scale)), tip_y - int(6 * scale)),
        ]
        pygame.draw.polygon(s, (195, 208, 228, min(255, alpha)), blade_pts)

        # Reflet central brillant (fuller / gorge)
        cen_pts = [
            (cx - max(1, blade_w // 7), cg_y),
            (cx + max(1, blade_w // 7), cg_y),
            (cx + max(1, int(1 * scale)), tip_y - int(10 * scale)),
            (cx - max(1, int(1 * scale)), tip_y - int(10 * scale)),
        ]
        pygame.draw.polygon(s, (255, 255, 255, min(255, alpha)), cen_pts)

        # Bords tranchants (éclat blanc-bleu)
        pygame.draw.line(s, (235, 248, 255, alpha),
                         (cx - blade_w // 2, cg_y), (cx, tip_y),
                         max(1, int(2 * scale)))
        pygame.draw.line(s, (235, 248, 255, alpha),
                         (cx + blade_w // 2, cg_y), (cx, tip_y),
                         max(1, int(2 * scale)))

        # Rainure centrale (fuller) — légère ombre longitudinale
        mid_y = (cg_y + tip_y) // 2
        pygame.draw.line(s, (148, 160, 185, min(175, alpha)),
                         (cx, cg_y + int(10 * scale)), (cx, mid_y + int(12 * scale)),
                         max(1, int(3 * scale)))

        # ── GARDE (crossguard) ────────────────────────────────────────────────
        cg_rect = pygame.Rect(cx - cg_w // 2, cg_y - cg_h // 2, cg_w, cg_h)
        # Corps doré
        pygame.draw.rect(s, (215, 170, 45, alpha), cg_rect,
                         border_radius=max(2, int(6 * scale)))
        # Reflet supérieur
        pygame.draw.rect(s, (255, 235, 125, min(255, alpha)),
                         pygame.Rect(cx - cg_w // 2 + 5, cg_y - cg_h // 2 + 2,
                                     cg_w - 10, max(2, cg_h // 3)),
                         border_radius=max(1, int(3 * scale)))
        # Ombre inférieure
        pygame.draw.rect(s, (135, 95, 18, min(200, alpha)),
                         pygame.Rect(cx - cg_w // 2 + 3, cg_y + cg_h // 5,
                                     cg_w - 6, max(2, cg_h // 3)),
                         border_radius=max(1, int(2 * scale)))
        # Bordure lumineuse
        pygame.draw.rect(s, (255, 218, 80, alpha), cg_rect,
                         max(1, int(2 * scale)),
                         border_radius=max(2, int(6 * scale)))
        # Gemmes violettes aux extrémités
        for gx in [cx - cg_w // 2 + int(9 * scale),
                   cx + cg_w // 2 - int(9 * scale)]:
            gr = max(3, int(7 * scale))
            pygame.draw.circle(s, (155, 55, 220, alpha), (gx, cg_y), gr)
            pygame.draw.circle(s, (220, 150, 255, min(190, alpha)),
                               (gx - max(1, gr // 3), cg_y - max(1, gr // 3)),
                               max(1, gr // 3))

        # ── POIGNÉE (grip) ─────────────────────────────────────────────────────
        grip_rect = pygame.Rect(cx - grip_w // 2, grip_top, grip_w, grip_len)
        # Cuir sombre
        pygame.draw.rect(s, (42, 28, 18, alpha), grip_rect,
                         border_radius=max(2, int(4 * scale)))
        # Ligatures (enroulements de cuir)
        for i in range(6):
            bind_y = grip_top + int(grip_len * (i + 0.5) / 6)
            pygame.draw.line(s, (75, 50, 28, min(200, alpha)),
                             (cx - grip_w // 2 - 1, bind_y),
                             (cx + grip_w // 2 + 1, bind_y),
                             max(1, int(2 * scale)))
        # Reflet sur la tranche
        pygame.draw.rect(s, (65, 45, 30, min(155, alpha)),
                         pygame.Rect(cx - grip_w // 4, grip_top + 2,
                                     grip_w // 2, grip_len - 4),
                         border_radius=max(1, int(3 * scale)))

        # ── POMMEAU ────────────────────────────────────────────────────────────
        pcx, pcy = cx, pommel_cy
        # Auréole dorée
        for pr_extra, pa in [(16, 40), (10, 65), (4, 95)]:
            pr = pommel_r + int(pr_extra * scale)
            pygame.draw.circle(s, (255, 215, 80, max(0, int(pa * progress))),
                               (pcx, pcy), pr, max(1, int(3 * scale)))
        # Corps
        pygame.draw.circle(s, (215, 170, 45, alpha), (pcx, pcy), pommel_r)
        # Spéculaire
        hl_r = max(2, pommel_r // 3)
        pygame.draw.circle(s, (255, 245, 165, min(230, alpha)),
                           (pcx - hl_r, pcy - hl_r), hl_r)
        # Contour
        pygame.draw.circle(s, (255, 215, 80, alpha), (pcx, pcy), pommel_r, 2)

        # ── RAYONS DE LUMIÈRE depuis la garde ─────────────────────────────────
        ra_alpha = max(0, min(255, int(72 * progress)))
        for angle_deg in range(0, 360, 22):
            angle = math.radians(angle_deg)
            r1 = int((cg_w // 2 + 6) * scale)
            r2 = int((cg_w // 2 + 30 + 7 * math.cos(angle * 5)) * scale)
            x1 = cx + int(r1 * math.cos(angle))
            y1 = cg_y + int(r1 * math.sin(angle))
            x2 = cx + int(r2 * math.cos(angle))
            y2 = cg_y + int(r2 * math.sin(angle))
            pygame.draw.line(s, (255, 242, 130, ra_alpha),
                             (x1, y1), (x2, y2),
                             max(1, int(2 * scale)))

        # ── ÉTINCELLES le long de la lame ─────────────────────────────────────
        if progress > 0.25:
            for _ in range(4):
                t_frac = random.uniform(0.05, 0.92)
                off_x  = random.uniform(-blade_w * t_frac / 2,
                                         blade_w * t_frac / 2)
                sp_x   = int(cx + off_x)
                sp_y   = cg_y + int((tip_y - cg_y) * t_frac)
                sp_r   = max(1, int(random.uniform(1.5, 3.5) * scale))
                sp_a   = max(0, min(255, int(random.uniform(170, 255) * progress)))
                pygame.draw.circle(s, (255, 255, 195, sp_a), (sp_x, sp_y), sp_r)

        self.screen.blit(s, (0, 0))

    def _draw_victory_overlay(self):
        """Simple fondu noir avant l'apparition d'Aegis."""
        t = self.final_blow_hub_t
        black_a = min(255, int(255 * t / 90.0))
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, black_a))
        self.screen.blit(veil, (0, 0))


def main():
    pygame.init()
    pygame.display.init()
    Game().run()
    sys.exit(0)


if __name__ == "__main__":
    main()
