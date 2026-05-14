#!/bin/bash

# ── Aller dans le dossier du script (compatible vieux macOS sans realpath) ──
cd "$(cd "$(dirname "$0")"; pwd)"

echo ""
echo " ================================"
echo "  DREAMSPAWN — Build Mac"
echo " ================================"
echo ""

# ── 1. Trouver Python 3 ──
PYTHON=""
for cmd in python3 python3.12 python3.11 python3.10 python; do
    if command -v $cmd &>/dev/null; then
        VERSION=$($cmd -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        if [ "$VERSION" = "3" ]; then
            PYTHON=$cmd
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
echo "✅ Python trouvé : $($PYTHON --version)"

# ── 2. Vérifier version Python >= 3.10 ──
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MINOR" -lt 10 ]; then
    echo "❌ Python trop vieux (besoin 3.10+, tu as 3.$PY_MINOR)"
    echo "   Installe une version récente sur https://www.python.org/downloads/"
    read -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

# ── 3. Installer pygame si absent ──
$PYTHON -c "import pygame" &>/dev/null || {
    echo "⚙️  Installation de pygame..."
    $PYTHON -m pip install pygame --quiet || $PYTHON -m pip install pygame-ce --quiet || {
        echo "❌ Impossible d'installer pygame (pas de connexion internet ?)"
        read -p "Appuie sur Entrée pour fermer..."
        exit 1
    }
}
echo "✅ pygame OK"

# ── 4. Installer PyInstaller si absent ──
$PYTHON -c "import PyInstaller" &>/dev/null || {
    echo "⚙️  Installation de PyInstaller..."
    $PYTHON -m pip install pyinstaller --quiet || {
        echo "❌ Impossible d'installer PyInstaller (pas de connexion internet ?)"
        read -p "Appuie sur Entrée pour fermer..."
        exit 1
    }
}
echo "✅ PyInstaller OK"

# ── 5. Vérifier que main.py existe ──
if [ ! -f "../src/main.py" ]; then
    echo "❌ Fichier main.py introuvable dans src/"
    read -p "Appuie sur Entrée pour fermer..."
    exit 1
fi

# ── 6. Vérifier que assets/ existe ──
ASSETS_FLAG=""
if [ -d "../assets" ]; then
    ASSETS_FLAG="--add-data ../assets:assets"
    echo "✅ Dossier assets/ trouvé"
else
    echo "⚠️  Dossier assets/ absent — le jeu compilera sans les images"
fi

# ── 7. Compiler ──
echo ""
echo "🚀 Compilation en cours..."
$PYTHON -m PyInstaller \
    --name Dreamspawn \
    --noconfirm \
    --windowed \
    --distpath dist \
    $ASSETS_FLAG \
    ../src/main.py

if [ $? -eq 0 ]; then
    # ── 8. Retirer la quarantaine macOS (Gatekeeper) ──
    xattr -rd com.apple.quarantine dist/Dreamspawn.app 2>/dev/null
    echo ""
    echo " ✅ Build terminé !"
    echo " 📍 Ton jeu est dans : build/dist/Dreamspawn.app"
else
    echo ""
    echo " ❌ Erreur lors de la compilation."
fi

echo ""
read -p "Appuie sur Entrée pour fermer..."
