# Headless-тест v1.4: render-глазки, solo, remove_disabled, diff-детектор
import bpy
import sys
import os
import importlib.util


def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a) + "\n")


spec = importlib.util.spec_from_file_location(
    "ofilter_test", r"D:\AI\ZCode\Project\FILTER\work\object_filter\__init__.py")
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)
dev.register()

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
a = bpy.context.active_object
a.name = "T_A"
bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
b = bpy.context.active_object
b.name = "T_B"
bpy.ops.mesh.primitive_cube_add(location=(6, 0, 0))
c = bpy.context.active_object
c.name = "T_C"
bpy.ops.object.empty_add(location=(9, 0, 0))
e = bpy.context.active_object
e.name = "T_E"

# --- 1. render toggle по типу ---
bpy.ops.vis.toggle_render(object_type='MESH')
out("1a render hidden (expect True True False):",
    a.hide_render, b.hide_render, e.hide_render)
bpy.ops.vis.toggle_render(object_type='MESH')
out("1b restored (expect False False):", a.hide_render, b.hide_render)

# --- 2. solo по типу ---
bpy.ops.vis.toggle_type(object_type='EMPTY', solo=True)
out("2a solo EMPTY (A hidden, E visible):",
    a.hide_viewport, e.hide_viewport)
bpy.ops.vis.toggle_type(object_type='MESH')  # вернуть меши
out("2b meshes back visible:", not a.hide_viewport and not b.hide_viewport)

# --- 3. remove_disabled ---
a.modifiers.new("KeepMe", 'BEVEL')
dis = a.modifiers.new("KillMe", 'BEVEL')
dis.show_viewport = False
res = bpy.ops.vis.remove_disabled(match_scope='SCENE')
out("3 remove_disabled:", res, "| A mods (expect ['KeepMe']):", list(a.modifiers.keys()))

# --- 4. diff-детектор ---
a.modifiers.new("Mirror", 'MIRROR')           # дефолт: axis X
b.modifiers.new("Mirror", 'MIRROR')           # такой же
c.modifiers.new("Mirror", 'MIRROR')
c.modifiers["Mirror"].mirror_object = b       # отличная настройка (pointer)

groups = dev.get_modifier_groups('NAME')
diffs = dev.get_group_diffs(groups, 'NAME', bpy.data.objects)
out("4a diffs (expect Mirror: 1):", diffs)

for o in bpy.data.objects:
    o.select_set(False)
res = bpy.ops.vis.select_mod_diffs(match_key='Mirror', match_by='NAME', match_scope='SCENE')
out("4b selected diff (expect T_C):", [o.name for o in bpy.data.objects if o.select_get()])

out("DONE-OK")
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
