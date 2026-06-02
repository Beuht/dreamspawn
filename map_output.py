# Généré par Dreamspawn Map Editor
# Coller dans main.py

def make_map_custom():
    platforms = []
    ground_y = 560

    platforms.append(Platform(-250,560,1900,200))
    platforms.append(Platform(120,470,220,18))
    platforms.append(Platform(940,470,220,18))
    platforms.append(Platform(540,360,200,18))
    platforms.append(Platform(360,250,140,18,dim_only=0))
    platforms.append(Platform(780,250,140,18,dim_only=1))
    platforms.append(Platform(-220,-200,100,1100))
    platforms.append(Platform(1500,-200,100,1100))

    spawn = (140, 556)
    return platforms, spawn
