# PROMPT — Note de passation (reprendre le dev de Dreamspawn)

> But de ce doc : donner le contexte à une **nouvelle session d'assistant** (ex. Claude
> sur un autre PC) pour continuer le développement là où on s'est arrêté.
> Lis-le en entier avant de coder. Les emplacements de code se trouvent par **nom de
> méthode** (`grep`), pas par numéro de ligne (ils bougent — `main.py` fait ~8 800 lignes).

---

## 🎮 Le projet
**Dreamspawn** — jeu de **boss-fight dark-fantasy** en **Python / pygame-ce**.
Tout le jeu tient dans **un seul fichier : `src/main.py`**.
- Boss final : **AEGIS** (le vrai boss, un dieu).
- Boss secondaire : **la Lune** (`MoonBoss`).

### Lancer
```bash
pip install pygame-ce
python src/main.py
```
- **Accès debug au combat Aegis** : sur l'écran-titre, taper **P** ~20 fois en <5 s (débloque le bouton).
- **God mode** : ouvrir le dialogue god → code **1234**. Donne PV pleins + dégâts ×4 + spam d'attaques (clic gauche tenu).

---

## 🧱 Architecture (`src/main.py`, repérer par `grep`)
- `class Player` — héros. `dimension` (DIM_REAL / DIM_DREAM), `can_swap` (la « Fissure »),
  `press_jump` / `try_dash` / `fire_bow`.
- `class MoonBoss` — boss Lune (5 phases, mécanique de dimension/rêve).
- `class AegisBoss` — **le boss final**. 2 PHASES visibles, mais le **design morphe avec les PV**.
- `class Game` — boucle principale : `run()`, `update_moon()`, `draw_world()`, états (`STATE_MOON`…).
- `make_moon_arena()` — l'arène (réutilisée par la Lune ET par Aegis).

---

## ✅ Ce qu'on a fait récemment (dernière session)
Tout tourne autour d'**AEGIS** et de ses **cinématiques** (scriptées, non-interactives,
gameplay gelé), plus la **vraie fin du jeu**.

1. **ENTRÉE grandiose** (~15 s) — `AegisBoss._update_intro` + `Game._draw_aegis_intro`.
   Descente, éveil (halo, fissures), carte-titre « AEGIS », le dieu parle.
2. **COURROUX** — cinématique d'attaque de la **phase 4** (~50 s).
   `_start_courroux` / `_update_courroux` + `Game._draw_courroux`.
   Masque qui se brise → **pression** (héros traîné au centre) → **météorite colossale**
   → écrasement. Frappe brutale mais **jamais létale**.
3. **NÉMÉSIS** — ouverture de la **phase 7** (~50 s).
   `_start_nemesis` / `_update_nemesis` + `Game._draw_nemesis`.
   Yeux rouges, héros soulevé, **trou noir + trou blanc**, swoosh caméra, lasers spammés,
   slam contre des pics, **énorme explosion** → héros à **1 PV**.
4. **LA FIN DU JEU** (canonique, après la mort en phase 7) — c'est **L'ENDING**, pas un secret :
   - **Faux-ending** (texte de mort) → une **FISSURE s'ouvre progressivement** + **2 mains
     griffues** déchirent l'écran.
   - **LE NÉANT** : dalle d'obsidienne + étoiles. **Dialogue** (le héros ne répond que « … »).
   - **SURVIE** : le héros a perdu ses pouvoirs (**esquive seule**), il est **increvable**
     (planché à 1 PV), une jauge **« ?! »** se remplit. **Pluie de MÉTÉORITES** à esquiver.
   - Jauge pleine → **clic** → **TIME-STOP** → grande **exécution cinématique (~34 s)** :
     caméra qui change de plan (gros plan du dieu, punch, **smash sur l'impact**, recul),
     **belle lame de lumière**, le dieu **coupé en deux** → carte-titre **« fin »** → texte final.
   - Méthodes : `_start_finale` / `_update_finale_cine` / `_finale_fire` (côté boss),
     et côté `Game` : `_draw_finale_world`, `_draw_finale` (dispatch),
     `_draw_finale_prelude` / `_dialogue` / `_survival` / `_timestop` / `_ending`,
     `_apply_finale_cam` (caméra), `_draw_light_blade`, `_draw_meteor`, `_draw_god_halves`,
     `_finale_activate_skill`. États : `boss.finale_active`, `boss.finale_act`
     (`prelude → dialogue → survival → timestop → ending`).
5. **2 phases visibles** : `phase_count = 2`, l'UI montre « Phase I / II ».
   COURROUX = bascule phase 1→2 (~57 % PV) ; NÉMÉSIS = finisher (~14 % PV).
   Le sprite/design morphe avec les PV. Difficulté des phases 4→7 relevée.
6. **SKIP des cinématiques** : pendant une cinématique non-jouable, **spammer Espace/Entrée**
   pour passer (petite jauge anti-skip-accidentel). `Game._skippable` / `_skip_cinematic` /
   `_skip_press`. ⚠️ La **survie** (jouable) n'est **pas** skippable.
7. **La Fissure (switch de dimension) = exclusive à la LUNE** (lore : Lune = rêve).
   Coupée pour Aegis (`player.can_swap = False` dans `start_aegis_fight`, et plateformes
   rendues visibles pour éviter les plateformes-rêve mortes).
8. Sprite d'Aegis **agrandi** ; les **noms d'attaques ne s'affichent plus** (les taunts du
   dieu restent) ; nombreux correctifs visuels (splat-art net, dais, fissure, mains, slash…).

---

## 🧪 Tester sans écran (headless)
Le jeu se pilote sans fenêtre via les pilotes SDL « dummy ». Pattern type d'un test :
```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame, importlib.util
spec = importlib.util.spec_from_file_location("m", "src/main.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
pygame.init(); pygame.font.init(); pygame.display.set_mode((m.WIDTH, m.HEIGHT))

g = m.Game(); g.start_aegis_fight(); b = g.boss
# Forcer une phase / déclencher une cinématique, ex. NÉMÉSIS (transition phase 7) :
thr = m.AEGIS_PHASE_THRESHOLDS
b.state = "fighting"; b.phase = 6; b.next_phase = 6
b.hp = int(b.max_hp_total * thr[7]) - 1
for _ in range(3300):
    g.update_moon(); g.draw_world(in_arena=True)
    pygame.image.save(g.screen, "/tmp/frame.png")   # capture pour vérif visuelle
```
- Compiler vite : `python -m py_compile src/main.py`.
- ⚠️ **Contrainte pygame** : une composante de couleur **> 255 plante** (`ValueError`).
  Toujours clamper l'alpha : `max(0, min(255, a))`.
- Les scripts de test de la session étaient dans `/tmp` (non commités) — à recréer au besoin.

---

## 📌 Conventions de travail
- **Aucun `git commit` / `git push` sans demande explicite du dev.**
- Réponses : **français (québécois informel)**, concises ; on **FAIT** d'abord, on **EXPLIQUE** ensuite (bullets courts).
- Vérifier (compile + repro headless + capture visuelle) avant de dire que c'est fait.
