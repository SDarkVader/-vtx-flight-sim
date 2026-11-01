import re

with open('public/vtx-env/airfield.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix sign materials so +Y and -Y have signMat
text = text.replace(
    'const mats = [boxMat, boxMat, boxMat, boxMat, signMat, boxMat];',
    'const mats = [boxMat, boxMat, signMat, signMat, boxMat, boxMat];'
)

# Fix hold position marking rotation
text = text.replace(
    '{ rot: ang + Math.PI / 2, z: Z + 0.003 }',
    '{ rot: ang, z: Z + 0.003 }'
)

# And make hold sign slightly larger and brighter
text = text.replace(
    'const box = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.25, 0.65), mats);',
    'const box = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.25, 0.85), mats);'
)

with open('public/vtx-env/airfield.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated sign and hold marking in airfield.js")
