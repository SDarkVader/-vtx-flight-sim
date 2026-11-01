with open('public/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = "import {enhanceAircraft} from './vtx-env/aircraft-look.js?v=1';"
replacement1 = target1 + "\nimport {buildVolcanoBasement} from './vtx-env/volcano-basement.js?v=1';"
assert target1 in text, "target1 not found"
text = text.replace(target1, replacement1)

target2 = "buildForecourt(scene,w);"
replacement2 = "buildForecourt(scene,w);environment.volcano=buildVolcanoBasement(scene,w);"
assert target2 in text, "target2 not found"
text = text.replace(target2, replacement2)

target3 = "environment.buildings?.update(now/1000);"
replacement3 = "environment.buildings?.update(now/1000);environment.volcano?.update(now/1000);"
assert target3 in text, "target3 not found"
text = text.replace(target3, replacement3)

with open('public/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("public/app.js patched successfully!")
