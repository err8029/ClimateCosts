"""Genera assets/logo.png: un icono sencillo de globo terráqueo para st.logo (que
necesita una imagen real, no admite un emoji directamente). Solo hace falta volver a
ejecutar esto si se quiere cambiar el diseño del icono.

Ejecutar desde la raíz del repositorio: python assets/generate_logo.py
"""
from PIL import Image, ImageDraw

size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

margin = 8
bbox = [margin, margin, size - margin, size - margin]

# Océano (círculo azul)
draw.ellipse(bbox, fill=(41, 121, 197, 255))

# Líneas de longitud/latitud (meridiano como elipse, un paralelo horizontal)
cx, cy = size // 2, size // 2
r = (size - margin * 2) // 2
draw.ellipse([cx - r * 0.5, cy - r, cx + r * 0.5, cy + r], outline=(255, 255, 255, 140), width=3)
draw.line([cx - r, cy, cx + r, cy], fill=(255, 255, 255, 140), width=3)

# Continentes (manchas verdes simples)
draw.ellipse([cx - r * 0.75, cy - r * 0.55, cx - r * 0.15, cy - r * 0.05], fill=(76, 175, 80, 255))
draw.ellipse([cx - r * 0.1, cy - r * 0.15, cx + r * 0.55, cy + r * 0.35], fill=(76, 175, 80, 255))
draw.ellipse([cx - r * 0.65, cy + r * 0.15, cx - r * 0.2, cy + r * 0.6], fill=(76, 175, 80, 255))
draw.ellipse([cx + r * 0.35, cy - r * 0.65, cx + r * 0.75, cy - r * 0.35], fill=(76, 175, 80, 255))

# Recortar al círculo del globo (evita que los continentes se salgan del borde)
mask = Image.new('L', (size, size), 0)
ImageDraw.Draw(mask).ellipse(bbox, fill=255)
img.putalpha(mask)

# Contorno del globo
draw.ellipse(bbox, outline=(20, 60, 100, 255), width=4)

img.save('assets/logo.png')
print("assets/logo.png generado.")
