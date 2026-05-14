#!/bin/bash

# ── Aller dans le dossier du script (compatible vieux macOS sans realpath) ──
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " ================================"
echo "  DREAMSPAWN — Build Mac"
echo " ================================"
echo ""
echo "📂 Dossier build : $SCRIPT_DIR"
echo ""

# ── 1. Trouver Python 3 ──
PYTHON=""
for cmd in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v $cmd &>/dev/null; then
        VERSION=$($cmd -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        if [ "$VERSION" = "3" ]; then
            PYTHON=$(command -v $cmd)
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3 introuvable !"
    echo "   Installe Python depuis https://www.python.org/downloads/"
    read -p "Appuie sur Entrée pour fermer..."
    exit 1
fi
echo "✅ Python : $($PYTHON --version) ($PYTHON)"

# ── 2. Vérifier version Python >= 3.10 ──
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MINOR" -lt 10 ] 2>/dev/null; then
    echo "❌ Python trop vieux (besoin 3.10+)"
    read -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

# ── 3. Installer pygame si absent ──
$PYTHON -c "import pygame" &>/dev/null || {
    echo "⚙️  Installation de pygame..."
    $PYTHON -m pip install pygame --quiet 2>&1 || \
    $PYTHON -m pip install pygame-ce --quiet 2>&1 || {
        echo "❌ Impossible d'installer pygame"
        read -p "Appuie sur Entrée pour fermer..."
        exit 1
    }
}
echo "✅ pygame OK"

# ── 4. Installer PyInstaller si absent ──
$PYTHON -c "import PyInstaller" &>/dev/null || {
    echo "⚙️  Installation de PyInstaller..."
    $PYTHON -m pip install pyinstaller --quiet 2>&1 || {
        echo "❌ Impossible d'installer PyInstaller"
        read -p "Appuie sur Entrée pour fermer..."
        exit 1
    }
}
echo "✅ PyInstaller OK"

# ── 5. Vérifier que main.py existe ──
MAIN_PY="$SCRIPT_DIR/../src/main.py"
if [ ! -f "$MAIN_PY" ]; then
    echo "❌ main.py introuvable : $MAIN_PY"
    echo "   Vérifie que la structure du dossier est correcte."
    read -p "Appuie sur Entrée pour fermer..."
    exit 1
fi
echo "✅ main.py trouvé"

# ── 6. Vérifier assets/ ──
ASSETS_DIR="$SCRIPT_DIR/../assets"
ASSETS_FLAG=""
if [ -d "$ASSETS_DIR" ]; then
    ASSETS_FLAG="--add-data $ASSETS_DIR:assets"
    echo "✅ assets/ trouvé"
else
    echo "⚠️  assets/ absent — compilation sans les images"
fi

# ── 7. Créer le dossier dist proprement ──
DIST_DIR="$SCRIPT_DIR/dist"
mkdir -p "$DIST_DIR"
echo "📦 Output : $DIST_DIR"

# ── 8. Compiler ──
echo ""
echo "🚀 Compilation en cours..."
$PYTHON -m PyInstaller \
    --name Dreamspawn \
    --noconfirm \
    --windowed \
    --distpath "$DIST_DIR" \
    --workpath "$SCRIPT_DIR/work" \
    --specpath "$SCRIPT_DIR" \
    $ASSETS_FLAG \
    "$MAIN_PY"

BUILD_RESULT=$?

# ── 9. Résultat ──
if [ $BUILD_RESULT -eq 0 ] && [ -d "$DIST_DIR/Dreamspawn.app" ]; then
    xattr -rd com.apple.quarantine "$DIST_DIR/Dreamspawn.app" 2>/dev/null
    echo ""
    echo " ✅ Build terminé !"
    echo " 📍 Ton .app est ici : $DIST_DIR/Dreamspawn.app"
    echo ""
    # Ouvre le dossier dist dans le Finder automatiquement
    open "$DIST_DIR"
else
    echo ""
    echo " ❌ Erreur lors de la compilation."
    echo " 📂 Vérifie les messages ci-dessus."
fi

echo ""
read -p "Appuie sur Entrée pour fermer..."
