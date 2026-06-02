#!/usr/bin/env python3
"""
Dreamspawn Map Editor
=====================
WASD / Flèches  : déplacer caméra      Molette         : zoom
G               : toggle grille        S               : toggle snap (10px)
Ctrl+S          : sauvegarder          Ctrl+O          : ouvrir
E               : exporter .py         Suppr / Backsp  : supprimer sélection
Echap           : désélectionner / annuler dessin

MODE SÉLECTION  : clic gauche = sélectionner + déplacer
MODE PLATEFORME : clic gauche + drag = dessiner une plateforme
MODE ASSET      : clic gauche = poser l'asset sélectionné
MODE SPAWN      : clic gauche = placer le spawn
Clic droit (tous modes) : sélectionner
Molette (asset sélectionné)   : changer l'échelle (partout)
[ / ]               : réduire / agrandir l'asset sélectionné
"""
import pygame, sys, os, json

# ── Bootstrap ─────────────────────────────────────────────────────────────────
pygame.init()

WIN_W, WIN_H = 1280, 720
PANEL_W      = 260
CANVAS_W     = WIN_W - PANEL_W   # 1020
TOOLBAR_H    = 40
STATUS_H     = 22
CANVAS_H     = WIN_H - TOOLBAR_H - STATUS_H  # 658

CANVAS_CLIP = pygame.Rect(0, TOOLBAR_H, CANVAS_W, CANVAS_H)

screen = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption("Dreamspawn Map Editor")
clock = pygame.time.Clock()

# ── Dimensions jeu ────────────────────────────────────────────────────────────
DIM_BOTH  = None
DIM_REAL  = 0
DIM_DREAM = 1

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = ( 18,  18,  25)
GRID_C      = ( 28,  28,  40)
GRIDM_C     = ( 45,  45,  60)
PNL_C       = ( 22,  22,  32)
SEP_C       = ( 40,  40,  55)
TBAR_C      = ( 18,  18,  28)
STAT_C      = ( 15,  15,  22)
TXT         = (210, 210, 228)
TXTD        = ( 88,  88, 115)
FLD         = ( 32,  32,  48)
FLDA        = ( 48,  48,  72)
BTN         = ( 40,  40,  58)
BTNH        = ( 58,  58,  80)
BTNA        = ( 76,  50, 145)
BTNR        = (145,  50,  60)   # rouge (supprimer)
BTNRH       = (175,  65,  75)
PC          = (120, 120, 148)   # plateforme both
PR          = ( 58, 108, 205)   # plateforme real
PD          = (152,  58, 205)   # plateforme dream
PG          = (168, 168, 200)   # ghost
SEL_P       = (255, 218,   0)   # sélection plateforme
SEL_A       = (255, 148,  38)   # sélection asset
SPW         = ( 68, 210,  68)
WHITE       = (255, 255, 255)

# ── Outils ────────────────────────────────────────────────────────────────────
T_SELECT, T_PLATFORM, T_ASSET, T_SPAWN = 0, 1, 2, 3
TOOL_NAMES = ["Sélection", "Plateforme", "Asset", "Spawn"]

# ── Assets ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DEFS = [
    ("bush-large",  "assets/maps/objects/bush-large.png"),
    ("bush-small",  "assets/maps/objects/bush-small.png"),
    ("statue",      "assets/maps/objects/statue.png"),
    ("stone-1",     "assets/maps/objects/stone-1.png"),
    ("stone-2",     "assets/maps/objects/stone-2.png"),
    ("stone-3",     "assets/maps/objects/stone-3.png"),
    ("stone-4",     "assets/maps/objects/stone-4.png"),
    ("tree-1",      "assets/maps/objects/tree-1.png"),
    ("tree-2",      "assets/maps/objects/tree-2.png"),
    ("tree-3",      "assets/maps/objects/tree-3.png"),
    ("background",  "assets/maps/tiles/background.png"),
    ("graveyard",   "assets/maps/tiles/graveyard.png"),
    ("mountains",   "assets/maps/tiles/mountains.png"),
    ("objects",     "assets/maps/tiles/objects.png"),
    ("tileset",     "assets/maps/tiles/tileset.png"),
]
THUMB_W, THUMB_H = 108, 66
ITEM_W,  ITEM_H  = 120, 84

ZOOM_MIN   = 0.06
ZOOM_MAX   = 6.0
GRID_SZ    = 50
SNAP_SZ    = 10
SCALE_STEP = 0.1
SCALE_MIN  = 0.1
SCALE_MAX  = 10.0

# ── Polices ───────────────────────────────────────────────────────────────────
def _make_font(size, bold=False):
    for name in ("Arial", "DejaVu Sans", "FreeSans", None):
        try:
            return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            pass
    return pygame.font.Font(None, size + 2)

FS  = _make_font(13)
FSB = _make_font(13, True)
FM  = _make_font(14, True)

# ── Petits helpers ────────────────────────────────────────────────────────────
def pc(dim):
    return PR if dim == DIM_REAL else PD if dim == DIM_DREAM else PC

def ds(dim):
    return "Réel" if dim == DIM_REAL else "Rêve" if dim == DIM_DREAM else "Les deux"

def blittext(surf, s, font, color, x, y):
    surf.blit(font.render(s, True, color), (int(x), int(y)))

def irect(r):
    return pygame.Rect(int(r.x), int(r.y), int(r.w), int(r.h))

def make_thumb_surf(img, name="?"):
    iw, ih = img.get_size()
    sc = min(THUMB_W / iw, THUMB_H / ih)
    nw, nh = max(1, int(iw * sc)), max(1, int(ih * sc))
    s = pygame.Surface((THUMB_W, THUMB_H), pygame.SRCALPHA)
    s.blit(pygame.transform.smoothscale(img, (nw, nh)),
           ((THUMB_W - nw) // 2, (THUMB_H - nh) // 2))
    return s

def slice_spritesheet(img, min_px=30):
    """
    Découpe automatiquement un sprite-sheet en sous-surfaces par régions opaques connexes.
    Retourne une liste de subsurfaces triées gauche→droite, haut→bas.
    """
    try:
        mask = pygame.mask.from_surface(img, threshold=15)
        components = mask.connected_components(min_px)
        if len(components) <= 1:
            return [img]
        rects = []
        for comp in components:
            brs = comp.get_bounding_rects()
            if brs:
                r = brs[0].unionall(brs[1:]) if len(brs) > 1 else brs[0]
                rects.append(r)
        rects.sort(key=lambda r: (r.y // 20, r.x))
        return [img.subsurface(r) for r in rects]
    except Exception:
        return [img]

def btn(surf, r, label, font=None, active=False, hover=False, danger=False):
    f = font or FS
    if danger:
        bg = BTNRH if hover else BTNR
    else:
        bg = BTNA if active else (BTNH if hover else BTN)
    pygame.draw.rect(surf, bg, r, border_radius=4)
    pygame.draw.rect(surf, SEP_C, r, 1, border_radius=4)
    t = f.render(label, True, WHITE)
    surf.blit(t, (r.x + (r.w-t.get_width())//2, r.y + (r.h-t.get_height())//2))


# ── Champ de saisie ───────────────────────────────────────────────────────────
class Field:
    def __init__(self, r, label="", floats=False):
        self.rect   = pygame.Rect(r)
        self.label  = label
        self.value  = "0"
        self.active = False
        self.floats = floats

    def hit(self, pos): return self.rect.collidepoint(pos)
    def focus(self):    self.active = True
    def blur(self):     self.active = False

    def keydown(self, ev):
        if not self.active: return None
        k = ev.key
        if k == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB, pygame.K_ESCAPE):
            self.active = False
            return "commit"
        else:
            c = ev.unicode
            if c.isdigit():
                self.value += c
            elif c == '-' and not self.value:
                self.value = '-'
            elif c == '.' and self.floats and '.' not in self.value:
                self.value += '.'
        return "editing"

    def get_int(self, d=0):
        try: return int(float(self.value))
        except: return d

    def get_float(self, d=1.0):
        try: return float(self.value)
        except: return d

    def setv(self, v):
        self.value  = f"{float(v):.2f}" if self.floats else str(int(v))
        self.active = False

    def draw(self, surf, mx=0, my=0):
        if self.label:
            blittext(surf, self.label, FS, TXTD,
                     self.rect.x, self.rect.y - 15)
        bg = FLDA if self.active else FLD
        pygame.draw.rect(surf, bg, self.rect, border_radius=3)
        pygame.draw.rect(surf, SEP_C, self.rect, 1, border_radius=3)
        cur = "|" if self.active and (pygame.time.get_ticks()//500)%2==0 else ""
        t = FS.render(self.value + cur, True, TXT)
        surf.blit(t, (self.rect.x+5, self.rect.y+(self.rect.h-t.get_height())//2))


# ── Éditeur ───────────────────────────────────────────────────────────────────
class Editor:

    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self):
        # Données
        self.platforms     = []  # [{"x","y","w","h","dim_only"}]
        self.assets_placed = []  # [{"file","x","y","scale"}]
        self.spawn         = [140, 556]

        # Caméra
        self.cam_x = -150.0
        self.cam_y = 100.0
        self.zoom  = 1.0

        # Options
        self.grid_on = True
        self.snap_on = True

        # Décor
        self.show_sky        = True
        self.show_mountains  = True
        self.show_ground     = True
        self.plat_style      = "none"   # "none" | "custom"
        self.plat_tex_img    = None     # surface utilisée pour tuiler les plateformes
        self.plat_tex_name   = ""       # nom affiché

        # Outil
        self.tool = T_SELECT

        # Sélection
        self.sel_type = None   # None | "plat" | "asset"
        self.sel_idx  = -1

        # Dessin plateforme
        self.drawing    = False
        self.draw_s     = (0, 0)   # start world
        self.draw_e     = (0, 0)   # end world (live)

        # Drag plateforme ou asset
        self.dragging        = False
        self.drag_mw_start   = (0.0, 0.0)  # mouse world au début du drag
        self.drag_obj_origin = (0, 0)       # position objet au début

        # Pan (milieu souris)
        self.panning    = False
        self.pan_ms     = (0, 0)    # mouse screen au début
        self.pan_cam    = (0.0, 0.0)

        # Asset sélectionné dans la bibliothèque
        self.lib_sel = 0

        # Images de décor (fond + texture sol)
        def _load_img(rel):
            try:
                return pygame.image.load(os.path.join(BASE_DIR, rel)).convert_alpha()
            except Exception:
                return None
        self.bg_sky       = _load_img("assets/maps/tiles/background.png")   # 384×224
        self.bg_mountains = _load_img("assets/maps/tiles/mountains.png")     # 192×179
        self.bg_ground    = _load_img("assets/maps/tiles/graveyard.png")     # 384×123

        # Thumbnails — auto-slicing des sprite-sheets
        self.thumbs = []  # [(name, thumb_surf, img_surf, ident)]
        for base_name, rel in ASSET_DEFS:
            full_path = os.path.join(BASE_DIR, rel)
            try:
                raw = pygame.image.load(full_path).convert_alpha()
                slices = slice_spritesheet(raw)
                if len(slices) == 1:
                    self.thumbs.append((base_name, make_thumb_surf(raw, base_name), raw, base_name))
                else:
                    for i, sub in enumerate(slices):
                        sname = f"{base_name}_{i+1}"
                        self.thumbs.append((sname, make_thumb_surf(sub, sname), sub, sname))
            except Exception:
                s = pygame.Surface((THUMB_W, THUMB_H), pygame.SRCALPHA)
                s.fill((60, 60, 95, 210))
                s.blit(FS.render(base_name[:14], True, TXT), (3, THUMB_H // 2 - 6))
                self.thumbs.append((base_name, s, None, base_name))

        # Scroll liste assets
        self.lib_scroll = 0

        # Polices déjà chargées globalement

        # ── Mise en page panneau (rects fixes, calculés une fois) ─────────────
        px = CANVAS_W + 8    # bord gauche du contenu
        pw = PANEL_W - 16    # largeur utile = 244
        fw = 114             # largeur d'un champ dans une paire
        f2 = px + 130        # x du champ droit

        # Toolbar
        ty, th_btn, tgap = 6, TOOLBAR_H-12, 4
        tx = 8
        def tb(w):
            nonlocal tx
            r = pygame.Rect(tx, ty, w, th_btn); tx += w+tgap; return r

        self.tb_new    = tb(72); self.tb_open = tb(60)
        self.tb_save   = tb(60); self.tb_exp  = tb(76)
        tx += 10
        self.tb_tools  = [tb(86 if i==1 else 72) for i in range(4)]
        tx += 10
        self.tb_grid   = tb(68); self.tb_snap = tb(62)

        # ── Panneau — section Propriétés (plus de section Outils, la toolbar suffit)
        py = TOOLBAR_H + 8
        self.pnl_props_lbl_y = py; py += 18

        # Champs position (partagés plateforme/asset)
        fy = py + 14
        self.f_x  = Field(pygame.Rect(px,  fy, fw, 22), "X")
        self.f_y  = Field(pygame.Rect(f2,  fy, fw, 22), "Y")
        py = fy + 22 + 12

        # Champs taille (plateforme) / échelle (asset)
        fy2 = py + 14
        self.f_w  = Field(pygame.Rect(px,  fy2, fw, 22), "L (largeur)")
        self.f_h  = Field(pygame.Rect(f2,  fy2, fw, 22), "H (hauteur)")
        self.f_sc = Field(pygame.Rect(px,  fy2, 148, 22), "Échelle", floats=True)
        self.pnl_sc_minus = pygame.Rect(px+156, fy2, 30, 22)
        self.pnl_sc_plus  = pygame.Rect(px+192, fy2, 30, 22)
        py = fy2 + 22 + 12

        # Boutons dimension (plateforme) / info+actions (asset)
        self.pnl_dim_lbl_y = py; py += 16
        self.pnl_dim_btns  = [
            (DIM_BOTH,  pygame.Rect(px, py,    pw, 24)),
            (DIM_REAL,  pygame.Rect(px, py+28, pw, 24)),
            (DIM_DREAM, pygame.Rect(px, py+56, pw, 24)),
        ]
        self.pnl_ast_info_y   = py
        self.pnl_ast_coll_btn = pygame.Rect(px, py+20, pw, 22)
        self.pnl_ast_del_btn  = pygame.Rect(px, py+46, pw, 24)
        py += 84 + 4

        # Séparateur
        self.pnl_sep2_y = py; py += 10

        # ── Section Décor
        self.pnl_decor_lbl_y = py; py += 18

        imp_w  = 32        # largeur bouton "📁"
        tog_w  = pw - imp_w - 4

        # Ciel
        self.pnl_sky_tog = pygame.Rect(px, py, tog_w, 22)
        self.pnl_sky_imp = pygame.Rect(px + tog_w + 4, py, imp_w, 22)
        py += 26
        # Montagnes
        self.pnl_mtn_tog = pygame.Rect(px, py, tog_w, 22)
        self.pnl_mtn_imp = pygame.Rect(px + tog_w + 4, py, imp_w, 22)
        py += 26
        # Sol
        self.pnl_gnd_tog = pygame.Rect(px, py, tog_w, 22)
        self.pnl_gnd_imp = pygame.Rect(px + tog_w + 4, py, imp_w, 22)
        py += 30

        # Texture plateformes — asset custom
        self.pnl_tex_lbl_y   = py; py += 14
        # [Aucune]  [← Choisir depuis biblio]  [✕]
        clr_w = 26
        set_w = pw - 70 - clr_w - 8
        self.pnl_tex_none_btn = pygame.Rect(px,                     py, 66,    22)
        self.pnl_tex_set_btn  = pygame.Rect(px + 70,               py, set_w, 22)
        self.pnl_tex_clr_btn  = pygame.Rect(px + pw - clr_w,       py, clr_w, 22)
        py += 26
        self.pnl_tex_prev_y = py   # y pour afficher le nom de la texture courante
        py += 16

        # Séparateur 3
        self.pnl_sep3_y = py; py += 10

        # Section Assets
        self.pnl_assets_lbl_y = py; py += 18
        self.pnl_assets_imp_btn = pygame.Rect(px, py, pw, 24)
        py += 28
        self.pnl_assets_top   = py
        self.pnl_assets_h     = WIN_H - STATUS_H - py

        # Tous les champs dans l'ordre pour routing clavier
        self.fields = [self.f_x, self.f_y, self.f_w, self.f_h, self.f_sc]

        # Fichier
        self.save_path = os.path.join(BASE_DIR, "map_save.json")
        self.status    = "Prêt  —  Ctrl+S sauvegarder  |  Ctrl+O ouvrir  |  E exporter"

        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.load_json(sys.argv[1])

    # ── Coordonnées ───────────────────────────────────────────────────────────

    def w2s(self, wx, wy):
        return ((wx - self.cam_x) * self.zoom,
                (wy - self.cam_y) * self.zoom + TOOLBAR_H)

    def s2w(self, sx, sy):
        return (sx / self.zoom + self.cam_x,
                (sy - TOOLBAR_H) / self.zoom + self.cam_y)

    def snap(self, v):
        return round(v / SNAP_SZ) * SNAP_SZ if self.snap_on else v

    def snap2(self, wx, wy):
        return self.snap(wx), self.snap(wy)

    def zoom_at(self, factor, sx, sy):
        wx, wy = self.s2w(sx, sy)
        self.zoom  = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        self.cam_x = wx - sx / self.zoom
        self.cam_y = wy - (sy - TOOLBAR_H) / self.zoom

    # ── Taille monde d'un asset ───────────────────────────────────────────────

    def asset_size(self, a):
        idx = self.lib_idx(a["file"])
        _, thumb, img, _ = self.thumbs[idx]
        src = img if img else thumb
        sc = a.get("scale", 1.0)
        iw, ih = src.get_size()
        return int(iw * sc), int(ih * sc)

    def lib_idx(self, identifier):
        for i, (name, _, _, ident) in enumerate(self.thumbs):
            if name == identifier or ident == identifier:
                return i
        # Compatibilité anciens saves (ex: "bush-large.png")
        stem = identifier.replace(".png", "").replace(".PNG", "")
        for i, (name, _, _, ident) in enumerate(self.thumbs):
            if name == stem or ident == stem or name.startswith(stem):
                return i
        return 0

    # ── Hit-test ──────────────────────────────────────────────────────────────

    def plat_at(self, wx, wy):
        for i in range(len(self.platforms)-1, -1, -1):
            p = self.platforms[i]
            if p["x"] <= wx < p["x"]+p["w"] and p["y"] <= wy < p["y"]+p["h"]:
                return i
        return -1

    def asset_at(self, wx, wy):
        for i in range(len(self.assets_placed)-1, -1, -1):
            a = self.assets_placed[i]
            aw, ah = self.asset_size(a)
            if a["x"] <= wx < a["x"]+aw and a["y"] <= wy < a["y"]+ah:
                return i
        return -1

    # ── Sélection ─────────────────────────────────────────────────────────────

    def select_plat(self, idx):
        self.sel_type = "plat"
        self.sel_idx  = idx
        if 0 <= idx < len(self.platforms):
            p = self.platforms[idx]
            self.f_x.setv(p["x"]); self.f_y.setv(p["y"])
            self.f_w.setv(p["w"]); self.f_h.setv(p["h"])

    def select_asset(self, idx):
        self.sel_type = "asset"
        self.sel_idx  = idx
        if 0 <= idx < len(self.assets_placed):
            a = self.assets_placed[idx]
            self.f_x.setv(a["x"]); self.f_y.setv(a["y"])
            self.f_sc.setv(a.get("scale", 1.0))

    def deselect(self):
        self.sel_type = None
        self.sel_idx  = -1
        for f in self.fields: f.blur()

    def commit_fields(self):
        if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
            p = self.platforms[self.sel_idx]
            p["x"] = self.f_x.get_int(p["x"])
            p["y"] = self.f_y.get_int(p["y"])
            p["w"] = max(1, self.f_w.get_int(p["w"]))
            p["h"] = max(1, self.f_h.get_int(p["h"]))
        elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            a = self.assets_placed[self.sel_idx]
            a["x"]     = self.f_x.get_int(a["x"])
            a["y"]     = self.f_y.get_int(a["y"])
            a["scale"] = max(SCALE_MIN, min(SCALE_MAX,
                             self.f_sc.get_float(a.get("scale", 1.0))))

    def delete_selected(self):
        if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
            self.platforms.pop(self.sel_idx)
            self.deselect()
        elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            self.assets_placed.pop(self.sel_idx)
            self.deselect()

    def scale_selected_asset(self, delta):
        if self.sel_type != "asset": return
        if not (0 <= self.sel_idx < len(self.assets_placed)): return
        a = self.assets_placed[self.sel_idx]
        a["scale"] = max(SCALE_MIN, min(SCALE_MAX,
                         round(a.get("scale", 1.0) + delta, 2)))
        self.f_sc.setv(a["scale"])

    # ── Gestion événements ────────────────────────────────────────────────────

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False

        mods = pygame.key.get_mods()
        ctrl = bool(mods & (pygame.KMOD_CTRL | pygame.KMOD_META))

        # ── Clavier
        if ev.type == pygame.KEYDOWN:
            # Champs actifs absorbent tout
            for f in self.fields:
                if f.active:
                    r = f.keydown(ev)
                    if r == "commit":
                        self.commit_fields()
                    return True

            if ctrl and ev.key == pygame.K_s: self.save_json(); return True
            if ctrl and ev.key == pygame.K_o: self.open_dialog(); return True
            if ev.key == pygame.K_e:          self.export_py();   return True
            if ev.key == pygame.K_g:
                self.grid_on = not self.grid_on; return True
            if ev.key == pygame.K_s and not ctrl:
                # 's' sans ctrl → snap toggle (sauf si champ actif — déjà géré)
                self.snap_on = not self.snap_on; return True
            if ev.key == pygame.K_LEFTBRACKET:
                self.scale_selected_asset(-SCALE_STEP); return True
            if ev.key == pygame.K_RIGHTBRACKET:
                self.scale_selected_asset(+SCALE_STEP); return True
            if ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self.delete_selected(); return True
            if ev.key == pygame.K_ESCAPE:
                self.deselect()
                self.drawing = False
                return True

        # ── Souris
        if ev.type == pygame.MOUSEBUTTONDOWN: return self.on_down(ev)
        if ev.type == pygame.MOUSEBUTTONUP:   return self.on_up(ev)
        if ev.type == pygame.MOUSEMOTION:     return self.on_move(ev)
        if ev.type == pygame.MOUSEWHEEL:      return self.on_wheel(ev)
        return True

    def on_down(self, ev):
        sx, sy = ev.pos
        btn_id = ev.button

        # Toolbar
        if sy < TOOLBAR_H:
            return self.click_toolbar(sx, sy, btn_id)

        # Panneau
        if sx >= CANVAS_W:
            return self.click_panel(sx, sy, btn_id)

        # Canvas
        if not CANVAS_CLIP.collidepoint(sx, sy):
            return True

        # Déactiver champs si clic canvas
        for f in self.fields:
            if f.active:
                f.blur()
                self.commit_fields()

        wx, wy = self.s2w(sx, sy)

        # Bouton milieu → pan
        if btn_id == 2:
            self.panning  = True
            self.pan_ms   = (sx, sy)
            self.pan_cam  = (self.cam_x, self.cam_y)
            return True

        # Clic droit → sélection
        if btn_id == 3:
            pi = self.plat_at(wx, wy)
            if pi >= 0:
                self.select_plat(pi)
            else:
                ai = self.asset_at(wx, wy)
                if ai >= 0:
                    self.select_asset(ai)
                else:
                    self.deselect()
            return True

        if btn_id != 1: return True

        # ── Clic gauche selon outil ─────────────────────────────────────────
        if self.tool == T_SELECT:
            pi = self.plat_at(wx, wy)
            if pi >= 0:
                self.select_plat(pi)
                self.dragging        = True
                self.drag_mw_start   = (wx, wy)
                p = self.platforms[pi]
                self.drag_obj_origin = (p["x"], p["y"])
            else:
                ai = self.asset_at(wx, wy)
                if ai >= 0:
                    self.select_asset(ai)
                    self.dragging        = True
                    self.drag_mw_start   = (wx, wy)
                    a = self.assets_placed[ai]
                    self.drag_obj_origin = (a["x"], a["y"])
                else:
                    self.deselect()

        elif self.tool == T_PLATFORM:
            # Si clic sur la plateforme sélectionnée → drag
            if (self.sel_type == "plat" and
                    0 <= self.sel_idx < len(self.platforms)):
                p = self.platforms[self.sel_idx]
                if (p["x"] <= wx < p["x"]+p["w"] and
                        p["y"] <= wy < p["y"]+p["h"]):
                    self.dragging        = True
                    self.drag_mw_start   = (wx, wy)
                    self.drag_obj_origin = (p["x"], p["y"])
                    return True
            # Sinon → dessiner
            self.drawing = True
            self.draw_s  = self.snap2(wx, wy)
            self.draw_e  = self.draw_s
            self.deselect()

        elif self.tool == T_ASSET:
            # Toujours poser un nouvel asset, puis basculer en sélection pour drag immédiat
            if self.lib_sel >= 0:
                name, _, _, ident = self.thumbs[self.lib_sel]
                ax, ay = self.snap2(wx, wy)
                self.assets_placed.append({
                    "file":  ident,
                    "x":     int(ax),
                    "y":     int(ay),
                    "scale": 1.0,
                })
                self.select_asset(len(self.assets_placed) - 1)
                # Drag immédiat + switch T_SELECT → repositionnable sans re-cliquer
                self.tool            = T_SELECT
                self.dragging        = True
                self.drag_mw_start   = (wx, wy)
                self.drag_obj_origin = (int(ax), int(ay))

        elif self.tool == T_SPAWN:
            sx2, sy2 = self.snap2(wx, wy)
            self.spawn  = [int(sx2), int(sy2)]
            self.status = f"Spawn → ({int(sx2)}, {int(sy2)})"

        return True

    def on_up(self, ev):
        if ev.button == 2:
            self.panning = False
            return True
        if ev.button == 1:
            # Fin de drag
            if self.dragging:
                self.dragging = False
                # Rafraîchir les champs
                if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
                    self.select_plat(self.sel_idx)
                elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
                    self.select_asset(self.sel_idx)

            # Fin de dessin
            if self.drawing:
                self.drawing = False
                x0, y0 = self.draw_s
                x1, y1 = self.draw_e
                rx, rw = min(x0,x1), abs(x1-x0)
                ry, rh = min(y0,y1), abs(y1-y0)
                if rw >= 4 and rh >= 4:
                    self.platforms.append({
                        "x": int(rx), "y": int(ry),
                        "w": int(rw), "h": int(rh),
                        "dim_only": DIM_BOTH,
                    })
                    self.select_plat(len(self.platforms) - 1)
        return True

    def on_move(self, ev):
        sx, sy = ev.pos

        if self.panning:
            dx = (sx - self.pan_ms[0]) / self.zoom
            dy = (sy - self.pan_ms[1]) / self.zoom
            self.cam_x = self.pan_cam[0] - dx
            self.cam_y = self.pan_cam[1] - dy
            return True

        if CANVAS_CLIP.collidepoint(sx, sy):
            wx, wy = self.s2w(sx, sy)

            if self.drawing:
                self.draw_e = self.snap2(wx, wy)

            if self.dragging:
                dx = wx - self.drag_mw_start[0]
                dy = wy - self.drag_mw_start[1]
                nx = self.snap(self.drag_obj_origin[0] + dx)
                ny = self.snap(self.drag_obj_origin[1] + dy)
                if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
                    p = self.platforms[self.sel_idx]
                    p["x"], p["y"] = int(nx), int(ny)
                    self.f_x.setv(p["x"]); self.f_y.setv(p["y"])
                elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
                    a = self.assets_placed[self.sel_idx]
                    a["x"], a["y"] = int(nx), int(ny)
                    self.f_x.setv(a["x"]); self.f_y.setv(a["y"])

        return True

    def on_wheel(self, ev):
        sx, sy = pygame.mouse.get_pos()

        # Scroll liste assets dans le panneau
        if sx >= CANVAS_W and sy >= self.pnl_assets_top:
            self.lib_scroll = max(0, self.lib_scroll - ev.y * 25)
            max_s = max(0, ((len(self.thumbs)+1)//2) * ITEM_H - self.pnl_assets_h)
            self.lib_scroll = min(self.lib_scroll, max_s)
            return True

        # Asset sélectionné → molette = échelle, peu importe où est le curseur
        if self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            self.scale_selected_asset(SCALE_STEP if ev.y > 0 else -SCALE_STEP)
            return True

        if not CANVAS_CLIP.collidepoint(sx, sy):
            return True

        # Sinon zoom caméra
        self.zoom_at(1.12 if ev.y > 0 else 1.0/1.12, sx, sy)
        return True

    # ── Clics toolbar ─────────────────────────────────────────────────────────

    def click_toolbar(self, sx, sy, btn_id):
        if btn_id != 1: return True
        mx, my = sx, sy
        if self.tb_new.collidepoint(mx, my):  self.new_map()
        elif self.tb_open.collidepoint(mx, my): self.open_dialog()
        elif self.tb_save.collidepoint(mx, my): self.save_json()
        elif self.tb_exp.collidepoint(mx, my):  self.export_py()
        elif self.tb_grid.collidepoint(mx, my): self.grid_on = not self.grid_on
        elif self.tb_snap.collidepoint(mx, my): self.snap_on = not self.snap_on
        else:
            for i, r in enumerate(self.tb_tools):
                if r.collidepoint(mx, my):
                    self.tool = i
                    if i == T_ASSET and self.lib_sel < 0:
                        self.lib_sel = 0
                    break
        return True

    # ── Clics panneau ─────────────────────────────────────────────────────────

    def click_panel(self, sx, sy, btn_id):
        if btn_id != 1: return True
        mx, my = sx, sy

        # 1. Champs de saisie
        for f in self.fields:
            if f.hit((mx, my)):
                # Valider les autres champs d'abord
                for g in self.fields:
                    if g is not f and g.active:
                        g.blur(); self.commit_fields()
                f.focus()
                return True
            elif f.active:
                f.blur(); self.commit_fields()

        # 3. Boutons selon sélection
        if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
            for dim_val, r in self.pnl_dim_btns:
                if r.collidepoint(mx, my):
                    self.platforms[self.sel_idx]["dim_only"] = dim_val
                    return True

        elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            if self.pnl_sc_minus.collidepoint(mx, my):
                self.scale_selected_asset(-SCALE_STEP); return True
            if self.pnl_sc_plus.collidepoint(mx, my):
                self.scale_selected_asset(+SCALE_STEP); return True
            if self.pnl_ast_coll_btn.collidepoint(mx, my):
                a = self.assets_placed[self.sel_idx]
                a["solid"] = not a.get("solid", False)
                return True
            if self.pnl_ast_del_btn.collidepoint(mx, my):
                self.delete_selected(); return True

        # 4. Boutons décor — toggles
        if self.pnl_sky_tog.collidepoint(mx, my):
            self.show_sky = not self.show_sky; return True
        if self.pnl_mtn_tog.collidepoint(mx, my):
            self.show_mountains = not self.show_mountains; return True
        if self.pnl_gnd_tog.collidepoint(mx, my):
            self.show_ground = not self.show_ground; return True
        # Boutons import
        if self.pnl_sky_imp.collidepoint(mx, my):
            self._import_bg("sky"); return True
        if self.pnl_mtn_imp.collidepoint(mx, my):
            self._import_bg("mountains"); return True
        if self.pnl_gnd_imp.collidepoint(mx, my):
            self._import_bg("ground"); return True
        # Texture plateformes
        if self.pnl_tex_none_btn.collidepoint(mx, my):
            self.plat_style = "none"; return True
        if self.pnl_tex_set_btn.collidepoint(mx, my):
            # Utilise l'asset actuellement sélectionné dans la bibliothèque comme texture
            if 0 <= self.lib_sel < len(self.thumbs):
                name, _, img, ident = self.thumbs[self.lib_sel]
                if img is not None:
                    self.plat_tex_img  = img
                    self.plat_tex_name = name
                    self.plat_style    = "custom"
                    self.status = f"Texture plateformes : {name}"
                else:
                    self.status = "Asset sans image (sprite-sheet non chargé)"
            return True
        if self.pnl_tex_clr_btn.collidepoint(mx, my):
            self.plat_tex_img  = None
            self.plat_tex_name = ""
            self.plat_style    = "none"
            self.status = "Texture plateformes effacée"
            return True

        # 5. Importer asset
        if self.pnl_assets_imp_btn.collidepoint(mx, my):
            self._import_asset(); return True

        # 6. Liste assets
        if sy >= self.pnl_assets_top:
            px = CANVAS_W + 8
            rel_y   = sy - self.pnl_assets_top + self.lib_scroll
            row     = int(rel_y) // ITEM_H
            local_x = sx - px
            col = 0 if 0 <= local_x < ITEM_W else (1 if ITEM_W+4 <= local_x < ITEM_W*2+4 else -1)
            if col >= 0:
                idx = row * 2 + col
                if 0 <= idx < len(self.thumbs):
                    self.lib_sel = idx
                    self.tool    = T_ASSET

        return True

    # ── Update (WASD) ─────────────────────────────────────────────────────────

    def update(self):
        if any(f.active for f in self.fields):
            return
        keys  = pygame.key.get_pressed()
        speed = 5 / self.zoom
        if keys[pygame.K_w] or keys[pygame.K_UP]:    self.cam_y -= speed
        if keys[pygame.K_DOWN]:                       self.cam_y += speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.cam_x -= speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.cam_x += speed
        # K_s est réservé au snap toggle (KEYDOWN), pas au mouvement

    # ── Dessin ────────────────────────────────────────────────────────────────

    def draw(self):
        screen.fill(BG)
        self.draw_canvas()
        self.draw_toolbar()
        self.draw_panel()
        self.draw_status()
        pygame.display.flip()

    # ── Canvas ────────────────────────────────────────────────────────────────

    def draw_canvas(self):
        screen.set_clip(CANVAS_CLIP)
        pygame.draw.rect(screen, BG, CANVAS_CLIP)

        self._draw_bg_layers()

        if self.grid_on:
            self.draw_grid()

        # Assets
        for i, a in enumerate(self.assets_placed):
            self.draw_asset(a, sel=(self.sel_type=="asset" and self.sel_idx==i))

        # Plateformes
        for i, p in enumerate(self.platforms):
            self.draw_plat(p, sel=(self.sel_type=="plat" and self.sel_idx==i))

        # Ghost dessin plateforme
        if self.drawing:
            x0, y0 = self.draw_s
            x1, y1 = self.draw_e
            rx, rw = min(x0,x1), abs(x1-x0)
            ry, rh = min(y0,y1), abs(y1-y0)
            if rw > 0 and rh > 0:
                gsx, gsy = self.w2s(rx, ry)
                gsw = max(1, int(rw*self.zoom))
                gsh = max(1, int(rh*self.zoom))
                ghost = pygame.Surface((gsw, gsh), pygame.SRCALPHA)
                ghost.fill((*PG, 70))
                screen.blit(ghost, (int(gsx), int(gsy)))
                pygame.draw.rect(screen, PG,
                                 pygame.Rect(int(gsx), int(gsy), gsw, gsh), 1)
                # Afficher les dimensions
                lbl = FS.render(f"{int(rw)} × {int(rh)}", True, WHITE)
                screen.blit(lbl, (int(gsx)+4, int(gsy)+4))

        # Spawn
        if self.spawn:
            spx, spy = self.w2s(*self.spawn)
            self.draw_spawn(spx, spy)

        # Preview asset en mode placement
        if self.tool == T_ASSET and 0 <= self.lib_sel < len(self.thumbs):
            mx, my = pygame.mouse.get_pos()
            if CANVAS_CLIP.collidepoint(mx, my):
                wx, wy = self.s2w(mx, my)
                snap_x, snap_y = self.snap2(wx, wy)
                psx, psy = self.w2s(snap_x, snap_y)
                _, thumb, img, _ = self.thumbs[self.lib_sel]
                src = img if img else thumb
                iw, ih = src.get_size()
                sw = max(1, int(iw*self.zoom))
                sh = max(1, int(ih*self.zoom))
                scaled = pygame.transform.scale(src, (sw, sh))
                scaled.set_alpha(140)
                screen.blit(scaled, (int(psx), int(psy)))

        screen.set_clip(None)
        # Séparateur canvas/panneau
        pygame.draw.line(screen, SEP_C,
                         (CANVAS_W, TOOLBAR_H), (CANVAS_W, WIN_H-STATUS_H))

    # ── Fonds parallaxe ───────────────────────────────────────────────────────

    def _draw_bg_layers(self):
        # 1. Ciel — remplit toute la hauteur du canvas
        if self.show_sky and self.bg_sky:
            bw, bh = self.bg_sky.get_size()
            sh = CANVAS_H
            sw = max(1, int(bw * sh / bh))
            scaled = pygame.transform.scale(self.bg_sky, (sw, sh))
            ox = int(-self.cam_x * 0.04 * self.zoom) % sw
            x = ox - sw
            while x < CANVAS_W:
                screen.blit(scaled, (x, TOOLBAR_H))
                x += sw

        # 2. Montagnes — mi-plan, ancrées au sol monde Y=560
        if self.show_mountains:
            self._tile_at_ground(self.bg_mountains, ground_wy=560, par=0.2, scale=2.0, alpha=210)

        # 3. Sol — premier plan, sol monde Y=560
        if self.show_ground:
            self._tile_at_ground(self.bg_ground, ground_wy=560, par=0.6, scale=2.0, alpha=255)

    def _tile_at_ground(self, img, ground_wy, par, scale=1.0, alpha=255):
        if not img: return
        iw, ih = img.get_size()
        sw = max(1, int(iw * scale * self.zoom))
        sh = max(1, int(ih * scale * self.zoom))
        scaled = pygame.transform.scale(img, (sw, sh))
        if alpha < 255:
            scaled.set_alpha(alpha)
        _, gsy = self.w2s(0, ground_wy)
        img_y = int(gsy) - sh
        ox = int(-self.cam_x * par * self.zoom) % sw
        x = ox - sw
        while x < CANVAS_W:
            screen.blit(scaled, (x, img_y))
            x += sw

    def draw_grid(self):
        wl, wt = self.s2w(0, TOOLBAR_H)
        wr, wb = self.s2w(CANVAS_W, WIN_H-STATUS_H)

        x = int(wl//GRID_SZ)*GRID_SZ
        while x < wr+GRID_SZ:
            gx, _ = self.w2s(x, 0)
            c = GRIDM_C if x % (GRID_SZ*4) == 0 else GRID_C
            pygame.draw.line(screen, c, (int(gx), TOOLBAR_H), (int(gx), WIN_H-STATUS_H))
            x += GRID_SZ

        y = int(wt//GRID_SZ)*GRID_SZ
        while y < wb+GRID_SZ:
            _, gy = self.w2s(0, y)
            c = GRIDM_C if y % (GRID_SZ*4) == 0 else GRID_C
            pygame.draw.line(screen, c, (0, int(gy)), (CANVAS_W, int(gy)))
            y += GRID_SZ

        ox, oy = self.w2s(0, 0)
        pygame.draw.line(screen, (55,55,75), (int(ox), TOOLBAR_H), (int(ox), WIN_H-STATUS_H))
        pygame.draw.line(screen, (55,55,75), (0, int(oy)), (CANVAS_W, int(oy)))

    def draw_plat(self, p, sel=False):
        sx, sy = self.w2s(p["x"], p["y"])
        sw = max(1, int(p["w"] * self.zoom))
        sh = max(1, int(p["h"] * self.zoom))
        if sw <= 0 or sh <= 0: return
        col = pc(p["dim_only"])
        r   = pygame.Rect(int(sx), int(sy), sw, sh)

        # Surface OPAQUE — pas de SRCALPHA pour éviter que le fond passe à travers
        EARTH = (36, 20, 8)
        surf = pygame.Surface((sw, sh))

        if self.plat_style == "custom" and self.plat_tex_img is not None:
            # 1. Base terre solide
            surf.fill(EARTH)
            # 2. Texture custom en haut (hauteur = min(plateforme, 80 monde))
            tw, th_img = self.plat_tex_img.get_size()
            tex_h_world = min(p["h"], 80)
            tex_w_world = max(1, tw * tex_h_world / th_img)
            tex_sw = max(1, int(tex_w_world * self.zoom))
            tex_sh = max(1, int(tex_h_world * self.zoom))
            tile = pygame.transform.scale(self.plat_tex_img, (tex_sw, tex_sh))
            # Offset ancré dans le monde (la texture ne "nage" pas au scroll)
            ox = -int((p["x"] % tex_w_world) * self.zoom)
            while ox > 0: ox -= tex_sw
            tx = ox
            while tx < sw:
                surf.blit(tile, (tx, 0))
                tx += tex_sw

        else:
            # "none" : couleur unie selon dimension
            surf.fill(col)

        # Tinte dimension (bleu/violet) si ce n'est pas "les deux"
        if p["dim_only"] is not None and self.plat_style != "none":
            tint = pygame.Surface((sw, sh))
            tint.fill(col)
            tint.set_alpha(55)
            surf.blit(tint, (0, 0))

        screen.blit(surf, r.topleft)
        pygame.draw.rect(screen, SEL_P if sel else col, r, 2 if sel else 1)
        if p["dim_only"] is not None and sw > 12 and sh > 12:
            pygame.draw.rect(screen, col, pygame.Rect(r.x+2, r.y+2, 6, 6))

    def draw_asset(self, a, sel=False):
        idx = self.lib_idx(a["file"])
        _, thumb, img, _ = self.thumbs[idx]
        src = img if img else thumb
        sc  = a.get("scale", 1.0)
        iw, ih = src.get_size()
        sw = max(1, int(iw*sc*self.zoom))
        sh = max(1, int(ih*sc*self.zoom))
        asx, asy = self.w2s(a["x"], a["y"])
        scaled = pygame.transform.scale(src, (sw, sh))
        screen.blit(scaled, (int(asx), int(asy)))
        if sel:
            pygame.draw.rect(screen, SEL_A,
                             pygame.Rect(int(asx), int(asy), sw, sh), 2)

    def draw_spawn(self, sx, sy):
        sz = max(5, int(10*self.zoom))
        ix, iy = int(sx), int(sy)
        pygame.draw.line(screen, SPW, (ix-sz, iy), (ix+sz, iy), 2)
        pygame.draw.line(screen, SPW, (ix, iy-sz), (ix, iy+sz), 2)
        pygame.draw.circle(screen, SPW, (ix, iy), max(2, sz//2), 2)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def draw_toolbar(self):
        pygame.draw.rect(screen, TBAR_C, pygame.Rect(0, 0, WIN_W, TOOLBAR_H))
        pygame.draw.line(screen, SEP_C, (0, TOOLBAR_H-1), (WIN_W, TOOLBAR_H-1))

        mx, my = pygame.mouse.get_pos()
        hover_tb = my < TOOLBAR_H

        for r, label in [(self.tb_new,"Nouveau"), (self.tb_open,"Ouvrir"),
                         (self.tb_save,"Sauver"),  (self.tb_exp,"Exporter")]:
            btn(screen, r, label, hover=hover_tb and r.collidepoint(mx,my))

        for i, r in enumerate(self.tb_tools):
            btn(screen, r, TOOL_NAMES[i],
                active=(self.tool==i),
                hover=hover_tb and r.collidepoint(mx,my) and self.tool!=i)

        btn(screen, self.tb_grid,
            "Grille ON" if self.grid_on else "Grille OFF",
            active=self.grid_on,
            hover=hover_tb and self.tb_grid.collidepoint(mx,my))

        btn(screen, self.tb_snap,
            "Snap ON" if self.snap_on else "Snap OFF",
            active=self.snap_on,
            hover=hover_tb and self.tb_snap.collidepoint(mx,my))

    # ── Panneau ───────────────────────────────────────────────────────────────

    def draw_panel(self):
        pygame.draw.rect(screen, PNL_C, pygame.Rect(CANVAS_W, 0, PANEL_W, WIN_H))

        px  = CANVAS_W + 8
        pw  = PANEL_W - 16
        mx, my = pygame.mouse.get_pos()

        # ── Propriétés
        blittext(screen, "PROPRIÉTÉS", FM, TXTD, px, self.pnl_props_lbl_y)

        if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
            p = self.platforms[self.sel_idx]
            self.f_x.label = "X"; self.f_y.label = "Y"
            self.f_x.draw(screen); self.f_y.draw(screen)
            self.f_w.draw(screen); self.f_h.draw(screen)

            blittext(screen, "Dimension :", FS, TXTD, px, self.pnl_dim_lbl_y)
            labels = ["Les deux", "Réel (bleu)", "Rêve (violet)"]
            for (dv, r), lbl in zip(self.pnl_dim_btns, labels):
                active = (p["dim_only"] == dv)
                col_act = pc(dv)
                bg = col_act if active else (BTNH if r.collidepoint(mx,my) else BTN)
                pygame.draw.rect(screen, bg, r, border_radius=4)
                pygame.draw.rect(screen, SEP_C, r, 1, border_radius=4)
                # radio dot
                cx2, cy2 = r.x+11, r.y+12
                pygame.draw.circle(screen, SEP_C, (cx2, cy2), 5)
                if active: pygame.draw.circle(screen, WHITE, (cx2, cy2), 3)
                blittext(screen, lbl, FS, WHITE, r.x+24, r.y+5)

        elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            a = self.assets_placed[self.sel_idx]
            self.f_x.label = "X"; self.f_y.label = "Y"
            self.f_x.draw(screen); self.f_y.draw(screen)
            self.f_sc.draw(screen)
            btn(screen, self.pnl_sc_minus, "−", FM,
                hover=self.pnl_sc_minus.collidepoint(mx,my))
            btn(screen, self.pnl_sc_plus,  "+", FM,
                hover=self.pnl_sc_plus.collidepoint(mx,my))
            aw, ah = self.asset_size(a)
            blittext(screen, f"{a['file']}  {aw}×{ah}px  ×{a.get('scale',1):.2f}",
                     FS, TXTD, px, self.pnl_ast_info_y)
            # Bouton collision
            solid = a.get("solid", False)
            coll_col = (40, 160, 80) if solid else BTN
            coll_lbl = "⬛ Collision ON" if solid else "⬜ Collision OFF"
            r_coll = self.pnl_ast_coll_btn
            pygame.draw.rect(screen, coll_col, r_coll, border_radius=4)
            pygame.draw.rect(screen, SEP_C, r_coll, 1, border_radius=4)
            blittext(screen, coll_lbl, FS, WHITE, r_coll.x+8, r_coll.y+5)
            btn(screen, self.pnl_ast_del_btn, "Supprimer l'asset  [Suppr]",
                hover=self.pnl_ast_del_btn.collidepoint(mx,my), danger=True)

        else:
            blittext(screen, "Rien de sélectionné", FS, TXTD,
                     px, self.pnl_props_lbl_y+18)
            blittext(screen, "← clic gauche ou clic droit", FS, TXTD,
                     px, self.pnl_props_lbl_y+34)

        pygame.draw.line(screen, SEP_C,
                         (CANVAS_W+4, self.pnl_sep2_y), (WIN_W-4, self.pnl_sep2_y))

        # ── Décor
        blittext(screen, "DÉCOR", FM, TXTD, px, self.pnl_decor_lbl_y)

        def bg_row(tog_r, imp_r, label, on):
            btn(screen, tog_r, ("▶ " if on else "⏸ ") + label,
                active=on, hover=(tog_r.collidepoint(mx, my) and not on))
            imp_hover = imp_r.collidepoint(mx, my)
            pygame.draw.rect(screen, BTNH if imp_hover else BTN, imp_r, border_radius=4)
            pygame.draw.rect(screen, SEP_C, imp_r, 1, border_radius=4)
            blittext(screen, "📁", FS, WHITE, imp_r.x+6, imp_r.y+4)

        bg_row(self.pnl_sky_tog, self.pnl_sky_imp, "Ciel",       self.show_sky)
        bg_row(self.pnl_mtn_tog, self.pnl_mtn_imp, "Montagnes",  self.show_mountains)
        bg_row(self.pnl_gnd_tog, self.pnl_gnd_imp, "Sol",        self.show_ground)

        blittext(screen, "Texture plateformes :", FS, TXTD, px, self.pnl_tex_lbl_y)
        # [Aucune]  [← Biblio]  [✕]
        btn(screen, self.pnl_tex_none_btn, "Aucune",
            active=(self.plat_style == "none"),
            hover=(self.pnl_tex_none_btn.collidepoint(mx, my) and self.plat_style != "none"))
        btn(screen, self.pnl_tex_set_btn, "← Biblio",
            active=(self.plat_style == "custom"),
            hover=(self.pnl_tex_set_btn.collidepoint(mx, my) and self.plat_style != "custom"))
        # Bouton effacer (rouge)
        clr_h = self.pnl_tex_clr_btn.collidepoint(mx, my)
        pygame.draw.rect(screen, BTNRH if clr_h else BTNR, self.pnl_tex_clr_btn, border_radius=4)
        pygame.draw.rect(screen, SEP_C, self.pnl_tex_clr_btn, 1, border_radius=4)
        blittext(screen, "✕", FS, WHITE,
                 self.pnl_tex_clr_btn.x + 5, self.pnl_tex_clr_btn.y + 4)
        # Nom de la texture active
        if self.plat_tex_name:
            short = self.plat_tex_name[:22] + "…" if len(self.plat_tex_name) > 22 else self.plat_tex_name
            blittext(screen, short, FS, TXT if self.plat_style == "custom" else TXTD,
                     px, self.pnl_tex_prev_y)
        else:
            blittext(screen, "— aucune —", FS, TXTD, px, self.pnl_tex_prev_y)

        pygame.draw.line(screen, SEP_C,
                         (CANVAS_W+4, self.pnl_sep3_y), (WIN_W-4, self.pnl_sep3_y))

        # ── Bibliothèque assets
        blittext(screen, "BIBLIOTHÈQUE", FM, TXTD, px, self.pnl_assets_lbl_y)
        btn(screen, self.pnl_assets_imp_btn, "➕  Importer une image…",
            hover=self.pnl_assets_imp_btn.collidepoint(mx, my))

        clip = pygame.Rect(CANVAS_W, self.pnl_assets_top, PANEL_W, self.pnl_assets_h)
        screen.set_clip(clip)

        for i, (name, thumb, _, _) in enumerate(self.thumbs):
            col_i = i % 2
            row_i = i // 2
            ix = px + col_i * (ITEM_W + 4)
            iy = self.pnl_assets_top + row_i * ITEM_H - self.lib_scroll
            if iy + ITEM_H < self.pnl_assets_top or iy > self.pnl_assets_top + self.pnl_assets_h:
                continue
            ir = pygame.Rect(ix-2, iy-2, ITEM_W+4, ITEM_H+4)
            sel_lib = (i == self.lib_sel)
            pygame.draw.rect(screen, (44,44,64) if sel_lib else (30,30,44), ir, border_radius=4)
            if sel_lib:
                pygame.draw.rect(screen, SEL_A, ir, 2, border_radius=4)
            screen.blit(thumb, (ix, iy))
            short = name[:12] + "…" if len(name)>12 else name
            screen.blit(FS.render(short, True, TXTD if not sel_lib else TXT),
                        (ix, iy+THUMB_H+2))

        screen.set_clip(None)

        # Scrollbar
        total_h = ((len(self.thumbs)+1)//2) * ITEM_H
        if total_h > self.pnl_assets_h:
            ratio = self.pnl_assets_h / total_h
            bar_h = max(18, int(self.pnl_assets_h * ratio))
            bar_y = self.pnl_assets_top + int(self.lib_scroll / total_h * self.pnl_assets_h)
            pygame.draw.rect(screen, SEP_C,
                             pygame.Rect(WIN_W-6, self.pnl_assets_top, 4, self.pnl_assets_h),
                             border_radius=2)
            pygame.draw.rect(screen, BTNA,
                             pygame.Rect(WIN_W-6, bar_y, 4, bar_h), border_radius=2)

    # ── Barre de statut ───────────────────────────────────────────────────────

    def draw_status(self):
        sr = pygame.Rect(0, WIN_H-STATUS_H, WIN_W, STATUS_H)
        pygame.draw.rect(screen, STAT_C, sr)
        pygame.draw.line(screen, SEP_C, (0, WIN_H-STATUS_H), (WIN_W, WIN_H-STATUS_H))

        mx, my = pygame.mouse.get_pos()
        if CANVAS_CLIP.collidepoint(mx, my):
            wx, wy = self.s2w(mx, my)
            snap_x, snap_y = self.snap2(wx, wy)
            coord = f"Monde ({int(wx)}, {int(wy)})  →  snap ({int(snap_x)}, {int(snap_y)})    Zoom {self.zoom:.2f}×"
        else:
            coord = f"Zoom {self.zoom:.2f}×"
        blittext(screen, coord, FS, TXTD, 8, WIN_H-STATUS_H+4)

        if self.sel_type == "plat" and 0 <= self.sel_idx < len(self.platforms):
            p = self.platforms[self.sel_idx]
            info = (f"Plateforme #{self.sel_idx}   "
                    f"({p['x']}, {p['y']})   "
                    f"{p['w']} × {p['h']} px   "
                    f"dim={ds(p['dim_only'])}")
            blittext(screen, info, FS, SEL_P, 380, WIN_H-STATUS_H+4)
        elif self.sel_type == "asset" and 0 <= self.sel_idx < len(self.assets_placed):
            a = self.assets_placed[self.sel_idx]
            aw, ah = self.asset_size(a)
            info = (f"Asset #{self.sel_idx}  {a['file']}   "
                    f"({a['x']}, {a['y']})   "
                    f"×{a.get('scale',1):.2f}   {aw}×{ah}px")
            blittext(screen, info, FS, SEL_A, 380, WIN_H-STATUS_H+4)
        else:
            blittext(screen, self.status, FS, TXTD, 380, WIN_H-STATUS_H+4)

        nb = f"{len(self.platforms)} plat.  {len(self.assets_placed)} assets"
        t  = FS.render(nb, True, TXTD)
        screen.blit(t, (CANVAS_W - t.get_width() - 8, WIN_H-STATUS_H+4))

    # ── Actions fichier ───────────────────────────────────────────────────────

    def new_map(self):
        self.platforms = []; self.assets_placed = []
        self.spawn = [140, 556]; self.deselect()
        self.status = "Nouvelle map."

    def save_json(self, path=None):
        path = path or self.save_path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "platforms": self.platforms,
                    "assets": [{"file":a["file"],"x":a["x"],"y":a["y"],
                                "scale":round(a.get("scale",1.0),4),
                                "solid":a.get("solid",False)}
                               for a in self.assets_placed],
                    "spawn": self.spawn,
                }, f, indent=2)
            self.save_path = path
            self.status = f"Sauvegardé → {os.path.basename(path)}"
        except Exception as e:
            self.status = f"Erreur sauvegarde : {e}"

    def load_json(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self.platforms = [{"x":int(p["x"]),"y":int(p["y"]),
                               "w":int(p["w"]),"h":int(p["h"]),
                               "dim_only":p.get("dim_only")}
                              for p in d.get("platforms", [])]
            self.assets_placed = [{"file":a["file"],"x":int(a.get("x",0)),
                                   "y":int(a.get("y",0)),
                                   "scale":float(a.get("scale",1.0)),
                                   "solid":bool(a.get("solid",False))}
                                  for a in d.get("assets", [])]
            sp = d.get("spawn", [140, 556])
            self.spawn = [int(sp[0]), int(sp[1])]
            self.deselect(); self.save_path = path
            self.status = f"Chargé → {os.path.basename(path)}"
        except Exception as e:
            self.status = f"Erreur chargement : {e}"

    # ── Dialogues fichiers (sans tkinter — crash SDL+macOS) ──────────────────

    @staticmethod
    def _pick_file(title, save=False, default_name="", image_mode=False):
        """
        Dialogue fichier compatible macOS + SDL.
        macOS  : osascript (natif, pas de conflit SDL/Cocoa)
        Autres : sous-processus Python isolé avec tkinter
        Retourne le chemin ou None si annulé.
        """
        import sys, subprocess, json as _json

        if sys.platform == "darwin":
            try:
                if save:
                    osa = (f'set f to choose file name with prompt "{title}"'
                           + (f' default name "{default_name}"' if default_name else "")
                           + "\nreturn POSIX path of f")
                else:
                    osa = f'set f to choose file with prompt "{title}"\nreturn POSIX path of f'
                r = subprocess.run(["osascript", "-e", osa],
                                   capture_output=True, text=True, timeout=120)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except Exception:
                pass
            return None

        # Windows / Linux : tkinter dans un sous-processus isolé
        script = """
import sys, json
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw()
    root.call('wm','attributes','.','-topmost',True)
    save = {save}
    title = {title}
    idir = {idir}
    ifile = {ifile}
    if save:
        p = filedialog.asksaveasfilename(title=title, initialdir=idir, initialfile=ifile)
    else:
        p = filedialog.askopenfilename(title=title, initialdir=idir)
    root.destroy()
    print(p or '', end='')
except Exception:
    print('', end='')
""".format(
            save=repr(save),
            title=_json.dumps(title),
            idir=_json.dumps(BASE_DIR),
            ifile=_json.dumps(default_name),
        )
        try:
            r = subprocess.run([sys.executable, "-c", script],
                               capture_output=True, text=True, timeout=120)
            path = r.stdout.strip()
            return path if path else None
        except Exception:
            return None

    def open_dialog(self):
        path = self._pick_file("Ouvrir carte — Dreamspawn Map Editor")
        if path:
            self.load_json(path)
        elif os.path.isfile(self.save_path):
            self.load_json(self.save_path)

    def _import_bg(self, layer):
        names = {"sky": "Ciel", "mountains": "Montagnes", "ground": "Sol"}
        path = self._pick_file(f"Importer image — {names.get(layer, layer)}")
        if path:
            try:
                img = pygame.image.load(path).convert_alpha()
            except Exception:
                try:
                    img = pygame.image.load(path).convert()
                except Exception as e:
                    self.status = f"Impossible de charger : {os.path.basename(path)}"
                    return
            if layer == "sky":         self.bg_sky       = img
            elif layer == "mountains": self.bg_mountains = img
            elif layer == "ground":    self.bg_ground    = img
            self.status = f"Image importée ({names.get(layer,'')}) : {os.path.basename(path)}"

    def _import_asset(self):
        """Importe une image externe et l'ajoute à la bibliothèque (avec auto-slice)."""
        path = self._pick_file("Importer un asset — Dreamspawn Map Editor")
        if not path:
            return
        try:
            raw = pygame.image.load(path).convert_alpha()
        except Exception:
            try:
                raw = pygame.image.load(path).convert()
            except Exception:
                self.status = f"Impossible de charger : {os.path.basename(path)}"
                return
        base_name = os.path.splitext(os.path.basename(path))[0]
        # Évite les doublons de nom
        existing_names = {t[0] for t in self.thumbs}
        suffix = 0
        unique = base_name
        while unique in existing_names:
            suffix += 1
            unique = f"{base_name}_{suffix}"
        base_name = unique
        # Auto-slice
        slices = slice_spritesheet(raw)
        added = 0
        if len(slices) == 1:
            self.thumbs.append((base_name, make_thumb_surf(raw, base_name), raw, base_name))
            added = 1
        else:
            for i, sub in enumerate(slices):
                sname = f"{base_name}_{i+1}"
                self.thumbs.append((sname, make_thumb_surf(sub, sname), sub, sname))
            added = len(slices)
        # Sélectionne le premier ajouté et passe en mode asset
        self.lib_sel  = len(self.thumbs) - added
        self.tool     = T_ASSET
        self.lib_scroll = max(0, (self.lib_sel // 2) * ITEM_H
                               - self.pnl_assets_h // 2)
        plural = f"{added} sprites" if added > 1 else "1 sprite"
        self.status = f"Importé : {base_name}  ({plural})"

    def export_py(self):
        out = os.path.join(BASE_DIR, "map_output.py")
        gy  = max((p["y"] for p in self.platforms), default=600,
                  key=lambda y: next((p["w"] for p in self.platforms if p["y"]==y), 0))
        lines = [
            "# Généré par Dreamspawn Map Editor",
            "# Coller dans main.py",
            "", "def make_map_custom():",
            "    platforms = []",
            f"    ground_y = {gy}", "",
        ]
        for p in self.platforms:
            d = p["dim_only"]
            if d is None:
                lines.append(f"    platforms.append(Platform({p['x']},{p['y']},{p['w']},{p['h']}))")
            else:
                lines.append(f"    platforms.append(Platform({p['x']},{p['y']},{p['w']},{p['h']},dim_only={d}))")
        if self.assets_placed:
            lines += ["", "    # Assets"]
            for a in self.assets_placed:
                sc = f"  ×{a['scale']:.2f}" if a.get("scale",1)!=1 else ""
                tag = "[COLLISION]" if a.get("solid") else "[déco]"
                lines.append(f"    # Asset {tag}: {a['file']} à ({a['x']},{a['y']}){sc}")
                if a.get("solid"):
                    idx = self.lib_idx(a["file"])
                    _, _, img, _ = self.thumbs[idx]
                    aw, ah = self.asset_size(a)
                    lines.append(f"    platforms.append(Platform({a['x']},{a['y']},{aw},{ah}))")
        sp = self.spawn or [140, gy-44]
        lines += ["", f"    spawn = ({sp[0]}, {sp[1]})",
                  "    return platforms, spawn", ""]
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.status = f"Exporté → {os.path.basename(out)}"
        except Exception as e:
            self.status = f"Erreur export : {e}"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ed = Editor()
    ed.platforms = [
        {"x":-200, "y":600, "w":1900, "h":200, "dim_only":None},
        {"x": 120, "y":470, "w": 220, "h": 18, "dim_only":None},
        {"x": 940, "y":470, "w": 220, "h": 18, "dim_only":None},
        {"x": 540, "y":360, "w": 200, "h": 18, "dim_only":None},
        {"x": 360, "y":250, "w": 140, "h": 18, "dim_only":DIM_REAL},
        {"x": 780, "y":250, "w": 140, "h": 18, "dim_only":DIM_DREAM},
        {"x":-220, "y":-200,"w": 100, "h":1100,"dim_only":None},
        {"x":1500, "y":-200,"w": 100, "h":1100,"dim_only":None},
    ]

    running = True
    while running:
        for ev in pygame.event.get():
            if not ed.handle(ev):
                running = False
        ed.update()
        ed.draw()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
