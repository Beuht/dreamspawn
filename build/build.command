#!/bin/bash
cd "$(dirname "$(realpath "$0")")"
echo ""
echo " ================================"
echo "  DREAMSPAWN — Build Mac"
echo " ================================"
echo ""

pip3 show pyinstaller > /dev/null 2>&1 || pip3 install pyinstaller

pyinstaller --name Dreamspawn --noconfirm --windowed --distpath dist --add-data "../assets:assets" ../src/main.py

echo ""
echo " Build terminé ! Retrouve ton .app dans build/dist/"
echo ""
read -p "Appuie sur Entrée pour fermer..."
