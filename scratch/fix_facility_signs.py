with open('public/vtx-env/buildings.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all sign material arrays so vertical faces (indices 2 and 3) use signMat
text = text.replace(
    '[darkWall, darkWall, darkWall, darkWall, signMat, darkWall]',
    '[darkWall, darkWall, signMat, signMat, darkWall, darkWall]'
)
text = text.replace(
    '[darkWall, darkWall, darkWall, darkWall, finchSign, darkWall]',
    '[darkWall, darkWall, finchSign, finchSign, darkWall, darkWall]'
)

with open('public/vtx-env/buildings.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated sign material face mapping in buildings.js")
