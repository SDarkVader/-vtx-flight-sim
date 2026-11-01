# Check holdpoint position and camera
p_hold = [-625, 28]
cam_pos = [-625, 12, 5.5] # camera is 16m south of hold point
cam_tgt = [-625, 32, 0.8] # looking 4m north of hold point
print(f"Camera distance to hold point: {((cam_pos[0]-p_hold[0])**2 + (cam_pos[1]-p_hold[1])**2)**0.5:.1f}m")
print(f"Viewing angle above ground: {5.5/16:.2f} rad = {57.3*5.5/16:.1f} deg")
