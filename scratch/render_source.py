import bpy
import math
from mathutils import Vector

scene = bpy.context.scene

# Camera
cam_data = bpy.data.cameras.new('RenderCam')
cam_data.lens = 45
cam_obj = bpy.data.objects.new('RenderCam', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_obj.location = Vector((4.8, -5.2, 3.2))
direction = Vector((0, 0, 1.2)) - cam_obj.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

# Lights
light_data = bpy.data.lights.new('Sun', type='SUN')
light_data.energy = 5.0
light_obj = bpy.data.objects.new('Sun', light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(50), math.radians(25), math.radians(-40))

scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = 'C:/Users/steve/.gemini/antigravity/brain/b329c633-e4ba-40e1-bf29-811ed0dfd8d8/test_source_render.png'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.engine = 'BLENDER_EEVEE'

bpy.ops.render.render(write_still=True)
print('RENDER SOURCE COMPLETE')
