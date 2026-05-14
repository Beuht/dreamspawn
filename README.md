# 🌙 DREAMSPAWN

> Metroidvania dark fantasy — combat de boss, exploration et changement de dimension.

---

## 🎮 C'est quoi ?

Dreamspawn est un jeu d'action/plateforme dark fantasy où tu affrontes **LA LUNE** — un boss en 5 phases de plus en plus brutales.

Le twist : tu peux basculer entre **deux dimensions** (Réel / Rêve) pour esquiver les attaques et survivre.

**Inspirations :** Hollow Knight, Cuphead, Undertale

---

## ⚙️ Installation

### Prérequis
- Python 3.10+
- pip

### Étapes

```bash
# 1. Cloner le projet
git clone git@github.com:Beuht/dreamspawn.git
cd dreamspawn

# 2. Installer les dépendances
pip install pygame

# 3. Lancer le jeu
python3 src/main.py
```

---

## 🕹️ Contrôles

| Action | Touche |
|---|---|
| Déplacement | Flèches / WASD / ZQSD |
| Saut | Espace |
| Double saut | Espace (x2 en l'air) |
| Changement de dimension | Espace (x3 en l'air) |
| Dash | Maj gauche |
| Tirer (arc) | Clic gauche (maintenir = charge) |
| Plein écran | F |
| Pause / Retour titre | Échap |
| Restart | R (après défaite) |

---

## 🌙 Le Boss — LA LUNE

5 phases progressives :

| Phase | Nom | Mécanique |
|---|---|---|
| 1 | L'Œil Insomniaque | Attaques dans les deux dimensions |
| 2 | La Marée | Change de dimension, attraction gravitationnelle |
| 3 | L'Éclipse | Rayons verticaux et horizontaux en croix |
| 4 | La Couronne Brisée | Fragments orbitaux à détruire |
| 5 | Le Croissant Inversé | Chorégraphie en 6 étapes, téléportation |

---

## 🔨 Compiler en .app / .exe

```bash
# Mac → double-clic sur :
build/build.command

# Windows → double-clic sur :
build/build.bat
```

Le fichier compilé apparaît dans `build/dist/`.

---

## 📁 Structure du projet

```
dreamspawn/
├── src/
│   └── main.py          ← jeu principal
├── assets/
│   ├── images/          ← sprites, backgrounds
│   ├── sounds/          ← musiques, sons
│   └── fonts/           ← polices
├── build/
│   ├── build.bat        ← compiler sur Windows
│   └── build.command    ← compiler sur Mac
├── bosses/              ← futurs modules boss
├── core/                ← futurs modules moteur
└── world/               ← futurs modules monde
```

---

## 🚧 Roadmap

- [x] Boss LA LUNE (5 phases)
- [ ] Zone de jeu explorable
- [ ] Histoire / dialogues
- [ ] Ennemis normaux
- [ ] Sauvegarde
- [ ] Direction artistique complète

---

*Projet en développement actif.*
