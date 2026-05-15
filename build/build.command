#!/bin/bash
# Double-clic sur ce fichier dans le Finder pour compiler Dreamspawn sur Mac.
# Requis : macOS 10.13+, connexion internet si Python/pip manquent.

# ── Aller dans le dossier du script ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " ================================================"
echo "  DREAMSPAWN - Build Mac"
echo " ================================================"
echo ""

# ── 1. Trouver Python 3.10+ ─────────────────────────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        MAJ=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        MIN=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$MAJ" = "3" ] && [ "$MIN" -ge 10 ] 2>/dev/null; then
            PYTHON=$(command -v "$cmd")
            break
        fi
    fi
done

# ── 2. Installation automatique de Python si absent ─────────────────────────
if [ -z "$PYTHON" ]; then
    echo " [!] Python 3.10+ introuvable. Tentative d installation automatique..."
    echo ""

    # Via Homebrew
    if command -v brew &>/dev/null; then
        echo "     Via Homebrew..."
        brew install python@3.12 && PYTHON=$(command -v python3.12 || command -v python3)
    fi

    # Via le pkg officiel (curl)
    if [ -z "$PYTHON" ]; then
        PKG_URL="https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg"
        echo "     Telechargement Python 3.12 depuis python.org..."
        curl -L -o /tmp/python_setup.pkg "$PKG_URL" && \
        sudo installer -pkg /tmp/python_setup.pkg -target / && \
        rm -f /tmp/python_setup.pkg && \
        PYTHON=$(command -v python3.12 || command -v python3)
    fi

    if [ -z "$PYTHON" ]; then
        echo ""
        echo " !! ECHEC : Python n a pas pu etre installe automatiquement."
        echo " Installe Python manuellement : https://www.python.org/downloads/"
        echo ""
        read -p "Appuie sur Entree pour fermer..."
        exit 1
    fi
fi

echo " Python trouve : $("$PYTHON" --version) ($PYTHON)"
echo ""

# ── 3. pip a jour ────────────────────────────────────────────────────────────
"$PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null

# ── 4. pygame-ce ─────────────────────────────────────────────────────────────
"$PYTHON" -c "import pygame" &>/dev/null || {
    echo " Installation de pygame-ce..."
    "$PYTHON" -m pip install pygame-ce || {
        echo " ERREUR : impossible d'installer pygame-ce."
        read -p "Appuie sur Entree pour fermer..."
        exit 1
    }
}
echo " pygame-ce OK"

# ── 5. PyInstaller ────────────────────────────────────────────────────────────
"$PYTHON" -c "import PyInstaller" &>/dev/null || {
    echo " Installation de PyInstaller..."
    "$PYTHON" -m pip install pyinstaller || {
        echo " ERREUR : impossible d'installer PyInstaller."
        read -p "Appuie sur Entree pour fermer..."
        exit 1
    }
}
echo " PyInstaller OK"
echo ""

# ── 6. Compilation ────────────────────────────────────────────────────────────
echo " Compilation en cours..."
echo ""

DIST_DIR="$SCRIPT_DIR/dist"
mkdir -p "$DIST_DIR"

"$PYTHON" -m PyInstaller \
    --name Dreamspawn \
    --noconfirm \
    --windowed \
    --onefile \
    --distpath "$DIST_DIR" \
    --workpath "$SCRIPT_DIR/work" \
    --specpath "$SCRIPT_DIR" \
    --add-data "../assets:assets" \
    --add-data "../assets/music:assets/music" \
    --add-data "../assets/sounds:assets/sounds" \
    "../src/main.py"

BUILD_RESULT=$?

# ── 7. Resultat ───────────────────────────────────────────────────────────────
if [ $BUILD_RESULT -eq 0 ]; then
    # Lever la quarantaine macOS (Gatekeeper) pour le .app ou le binaire
    find "$DIST_DIR" -name "Dreamspawn*" -exec xattr -rd com.apple.quarantine {} \; 2>/dev/null
    echo ""
    echo " ================================================"
    echo "  Build termine !"
    if [ -d "$DIST_DIR/Dreamspawn.app" ]; then
        echo "  Ton .app est ici :"
        echo "  $DIST_DIR/Dreamspawn.app"
    else
        echo "  Ton binaire est ici :"
        echo "  $DIST_DIR/Dreamspawn"
    fi
    echo " ================================================"
    echo ""
    open "$DIST_DIR"
else
    echo ""
    echo " ================================================"
    echo "  ERREUR : le build a echoue."
    echo "  Lis les messages ci-dessus pour le detail."
    echo " ================================================"
    echo ""
fi

read -p "Appuie sur Entree pour fermer..."
