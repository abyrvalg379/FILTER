# ObjectFilter — Blender Extension
# Metadata in blender_manifest.toml

import bpy
import os
import tomllib
from collections import Counter


# --- Version (from manifest, for the panel header) ---

def _load_version():
    try:
        manifest = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        with open(manifest, "rb") as f:
            data = tomllib.load(f)
        return str(data["version"])
    except Exception:
        return ""

_ADDON_VERSION = _load_version()
_PANEL_LABEL = f"FILTER v{_ADDON_VERSION}" if _ADDON_VERSION else "FILTER"
_PLACEHOLDER_OK = bpy.app.version >= (4, 3, 0)


# --- Helpers ---

def get_type_count(obj_type):
    return sum(1 for obj in bpy.data.objects if obj.type == obj_type)


def get_collection_obj_count(collection):
    return len(collection.objects)


def get_visible_count(obj_type=None, collection=None):
    if collection:
        return sum(1 for obj in collection.objects if not obj.hide_viewport)
    if obj_type:
        return sum(1 for obj in bpy.data.objects if obj.type == obj_type and not obj.hide_viewport)
    return 0


def is_type_hidden(obj_type):
    for obj in bpy.data.objects:
        if obj.type == obj_type and not obj.hide_viewport:
            return False
    return True


def is_type_render_hidden(obj_type):
    for obj in bpy.data.objects:
        if obj.type == obj_type and not obj.hide_render:
            return False
    return True


def is_type_select_disabled(obj_type):
    for obj in bpy.data.objects:
        if obj.type == obj_type and not obj.hide_select:
            return False
    return True


def iter_layer_collections(layer_coll):
    yield layer_coll
    for child in layer_coll.children:
        yield from iter_layer_collections(child)


def get_layer_collection(context, collection):
    """LayerCollection instance of a collection in the current view layer."""
    for lc in iter_layer_collections(context.view_layer.layer_collection):
        if lc.collection == collection:
            return lc
    return None


def is_visible_in_viewport(context, obj):
    """Object is actually visible in the viewport: composes object-level
    hide_viewport with view-layer collection hides (the outliner eye)."""
    if obj.name not in context.view_layer.objects or obj.hide_viewport:
        return False
    try:
        return obj.visible_get()
    except RuntimeError:
        return True


# --- Modifier helpers ---

MOD_ICONS = {
    'BEVEL': 'MOD_BEVEL',
    'SUBSURF': 'MOD_SUBSURF',
    'SOLIDIFY': 'MOD_SOLIDIFY',
    'MIRROR': 'MOD_MIRROR',
    'ARRAY': 'MOD_ARRAY',
    'BOOLEAN': 'MOD_BOOLEAN',
    'WEIGHTED_NORMAL': 'MOD_NORMALEDIT',
    'WELD': 'AUTOMERGE_ON',
    'DECIMATE': 'MOD_DECIM',
    'SHRINKWRAP': 'MOD_SHRINKWRAP',
    'DISPLACE': 'MOD_DISPLACE',
    'ARMATURE': 'MOD_ARMATURE',
    'SKIN': 'MOD_SKIN',
    'TRIANGULATE': 'MOD_TRIANGULATE',
}


def _valid_icon_names():
    try:
        prop = bpy.types.UILayout.bl_rna.functions['label'].parameters['icon']
        return {i.identifier for i in prop.enum_items}
    except Exception:
        return None


_VALID_ICONS = _valid_icon_names()


def get_mod_icon(mod_type):
    icon = MOD_ICONS.get(mod_type, 'MODIFIER')
    # невалидное имя иконки убивает весь draw панели — откат на безопасное
    if _VALID_ICONS is not None and icon not in _VALID_ICONS:
        return 'MODIFIER'
    return icon


def iter_scope_objects(context, scope):
    """Objects the By Modifier section operates on."""
    if scope == 'SELECTED':
        return context.selected_objects
    return bpy.data.objects


def get_modifier_groups(mode='NAME', objects=None):
    """Group modifiers by exact name or by type.

    Returns list of (key, display, mod_type, object_count),
    sorted alphabetically. Objects are counted once per group.
    """
    if objects is None:
        objects = bpy.data.objects
    groups = {}
    for obj in objects:
        seen = set()
        for mod in obj.modifiers:
            key = mod.name if mode == 'NAME' else mod.type
            if key in seen:
                continue
            seen.add(key)
            g = groups.setdefault(key, {'type': mod.type, 'count': 0})
            g['count'] += 1

    result = []
    for key, g in groups.items():
        if mode == 'NAME':
            display = key
        else:
            display = key.replace('_', ' ').title()
        result.append((key, display, g['type'], g['count']))
    result.sort(key=lambda item: item[1].lower())
    return result


# настройки, которые не считаются «смыслом» модификатора при сверке
# (is_active — UI-стейт активного модификатора стека, не настройка)
_FP_SKIP_PROPS = {'name', 'type', 'show_expanded', 'show_viewport',
                  'show_render', 'show_in_editmode', 'use_pin_to_last',
                  'is_active'}


def mod_fingerprint(mod):
    """Stable fingerprint of the modifier's meaningful settings."""
    fp = []
    for p in mod.bl_rna.properties:
        pid = p.identifier
        if pid in _FP_SKIP_PROPS or p.is_readonly:
            continue
        try:
            val = getattr(mod, pid)
        except AttributeError:
            continue
        is_array = getattr(p, 'is_array', False)
        if p.type == 'POINTER':
            fp.append((pid, val.name) if val else (pid, None))
        elif p.type == 'BOOLEAN' and is_array:
            fp.append((pid, tuple(val)))
        elif p.type == 'FLOAT':
            fp.append((pid, tuple(round(x, 5) for x in val) if is_array else round(val, 5)))
        elif p.type == 'INT' and is_array:
            fp.append((pid, tuple(val)))
        else:
            fp.append((pid, val))
    return tuple(fp)


def get_group_diffs(mod_groups, mode, objects):
    """{group key: number of objects whose modifier settings differ
    from the majority of the group}."""
    diffs = {}
    for key, display, mod_type, count in mod_groups:
        fps = []
        for obj in objects:
            if obj.library is not None:
                continue
            for mod in obj.modifiers:
                if (mode == 'NAME' and mod.name == key) or \
                   (mode == 'TYPE' and mod.type == key):
                    fps.append(mod_fingerprint(mod))
                    break
        if len(fps) > 1:
            common = Counter(fps).most_common(1)[0][0]
            outliers = sum(1 for f in fps if f != common)
            if outliers:
                diffs[key] = outliers
    return diffs


# --- Panel (parent header) ---

class VIS_PT_panel(bpy.types.Panel):
    bl_label = _PANEL_LABEL
    bl_idname = "VIS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"

    def draw(self, context):
        pass  # только шапка с версией, содержимое — в суб-панелях


class VIS_PT_type(bpy.types.Panel):
    bl_label = "By Type"
    bl_idname = "VIS_PT_type"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"
    bl_parent_id = "VIS_PT_panel"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        types = [
            ('MESH', 'Mesh', 'MESH_DATA'),
            ('ARMATURE', 'Armature', 'ARMATURE_DATA'),
            ('EMPTY', 'Empty', 'EMPTY_DATA'),
            ('LIGHT', 'Light', 'LIGHT'),
            ('CAMERA', 'Camera', 'CAMERA_DATA'),
        ]

        for obj_type, label, icon in types:
            total = get_type_count(obj_type)
            visible = get_visible_count(obj_type=obj_type)
            locked = is_type_select_disabled(obj_type)
            render_hidden = is_type_render_hidden(obj_type)

            split = layout.split(factor=0.45, align=True)
            split.label(text=f"{label} ({visible}/{total})", icon=icon)

            sub = split.row(align=True)
            sub.alignment = 'RIGHT'
            sub.enabled = total > 0
            sub.operator("vis.select_type", text="\u25ce").object_type = obj_type
            sub.operator("vis.toggle_type", text="",
                         icon='HIDE_ON' if visible == 0 else 'HIDE_OFF',
                         depress=visible == 0).object_type = obj_type
            sub.operator("vis.toggle_render", text="",
                         icon='RESTRICT_RENDER_ON' if render_hidden else 'RESTRICT_RENDER_OFF',
                         depress=render_hidden).object_type = obj_type
            sub.operator("vis.lock_type", text="",
                         icon='RESTRICT_SELECT_ON' if locked else 'RESTRICT_SELECT_OFF',
                         depress=locked).object_type = obj_type


class VIS_PT_name(bpy.types.Panel):
    bl_label = "By Name"
    bl_idname = "VIS_PT_name"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"
    bl_parent_id = "VIS_PT_panel"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        if _PLACEHOLDER_OK:
            layout.prop(context.scene, "vis_name_pattern", text="", icon='VIEWZOOM',
                        placeholder="Name pattern")
        else:
            layout.prop(context.scene, "vis_name_pattern", text="", icon='VIEWZOOM')

        row2 = layout.row(align=True)
        row2.operator("vis.toggle_name", text="Toggle", icon='HIDE_OFF')
        row2.operator("vis.select_name", text="Select", icon='RESTRICT_SELECT_OFF')


class VIS_PT_collections(bpy.types.Panel):
    bl_label = "Collections"
    bl_idname = "VIS_PT_collections"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"
    bl_parent_id = "VIS_PT_panel"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        for collection in bpy.data.collections:
            total = get_collection_obj_count(collection)
            if total == 0:
                continue

            lc = get_layer_collection(context, collection)
            if lc is not None:
                hidden = lc.hide_viewport
                visible = 0 if hidden else get_visible_count(collection=collection)
            else:
                hidden = not collection.objects or all(
                    obj.hide_viewport for obj in collection.objects)
                visible = get_visible_count(collection=collection)
            render_hidden = collection.hide_render

            split = layout.split(factor=0.45, align=True)
            split.label(text=f"{collection.name} ({visible}/{total})")

            sub = split.row(align=True)
            sub.alignment = 'RIGHT'
            sub.operator("vis.select_collection", text="\u25ce").collection_name = collection.name
            sub.operator("vis.toggle_collection", text="",
                         icon='HIDE_ON' if hidden else 'HIDE_OFF',
                         depress=hidden).collection_name = collection.name
            sub.operator("vis.toggle_render", text="",
                         icon='RESTRICT_RENDER_ON' if render_hidden else 'RESTRICT_RENDER_OFF',
                         depress=render_hidden).collection_name = collection.name


class VIS_PT_modifiers(bpy.types.Panel):
    bl_label = "By Modifier"
    bl_idname = "VIS_PT_modifiers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"
    bl_parent_id = "VIS_PT_panel"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        mod_mode = context.scene.vis_mod_mode
        mod_scope = context.scene.vis_mod_scope
        show_diffs = context.scene.vis_mod_show_diffs
        scope_objects = iter_scope_objects(context, mod_scope)
        mod_groups = get_modifier_groups(mod_mode, scope_objects)

        head = layout.row(align=True)
        head.prop(context.scene, "vis_mod_scope", text="")
        head.prop(context.scene, "vis_mod_mode", text="")
        head.prop(context.scene, "vis_mod_show_diffs", text="", icon='ERROR', toggle=True)

        if not mod_groups:
            if mod_scope == 'SELECTED':
                if not context.selected_objects:
                    layout.label(text="Nothing selected", icon='INFO')
                else:
                    layout.label(text="No modifiers on selected", icon='INFO')
            return

        group_diffs = get_group_diffs(mod_groups, mod_mode, scope_objects) if show_diffs else {}

        for key, display, mod_type, count in mod_groups:
            split = layout.split(factor=0.45, align=True)
            split.label(text=f"{display} ({count})", icon=get_mod_icon(mod_type))

            sub = split.row(align=True)
            sub.alignment = 'RIGHT'
            op_sel = sub.operator("vis.select_mods", text="\u25ce")
            op_sel.match_key = key
            op_sel.match_by = mod_mode
            op_sel.match_scope = mod_scope
            op_app = sub.operator("vis.apply_mod", text="", icon='CHECKMARK')
            op_app.match_key = key
            op_app.match_by = mod_mode
            op_app.match_scope = mod_scope
            op_del = sub.operator("vis.remove_mod", text="", icon='X')
            op_del.match_key = key
            op_del.match_by = mod_mode
            op_del.match_scope = mod_scope

            outliers = group_diffs.get(key, 0)
            if outliers:
                dsplit = layout.split(factor=0.45, align=True)
                dsplit.label(text="")
                dsub = dsplit.row(align=True)
                dsub.alignment = 'RIGHT'
                dsub.label(text=f"{outliers} of {count} differ", icon='ERROR')
                op_dif = dsub.operator("vis.select_mod_diffs", text="\u25ce")
                op_dif.match_key = key
                op_dif.match_by = mod_mode
                op_dif.match_scope = mod_scope

        disabled = 0
        for obj in scope_objects:
            if obj.library is None:
                disabled += sum(1 for m in obj.modifiers if not m.show_viewport)
        if disabled:
            op_dis = layout.operator("vis.remove_disabled",
                                     text=f"Remove disabled ({disabled})", icon='X')
            op_dis.match_scope = mod_scope


# --- Operators: Toggle Type ---

class VIS_OT_toggle_type(bpy.types.Operator):
    bl_idname = "vis.toggle_type"
    bl_label = "Toggle Type Visibility"
    bl_description = ("Hide/show all objects of this type (viewport and render). "
                      "Shift+Click: solo — hide everything except this type")
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()
    solo: bpy.props.BoolProperty(
        name="Solo",
        description="Hide everything except this type",
        default=False,
    )

    def invoke(self, context, event):
        self.solo = event.shift
        return self.execute(context)

    def execute(self, context):
        if self.solo:
            for obj in bpy.data.objects:
                want = obj.type == self.object_type
                obj.hide_viewport = not want
                obj.hide_render = not want
            self.report({'INFO'}, f"Solo {self.object_type.title()}: everything else hidden")
            return {'FINISHED'}

        hidden = is_type_hidden(self.object_type)
        for obj in bpy.data.objects:
            if obj.type == self.object_type:
                obj.hide_viewport = not hidden
                obj.hide_render = not hidden
        return {'FINISHED'}


# --- Operators: Select Type ---

class VIS_OT_select_type(bpy.types.Operator):
    bl_idname = "vis.select_type"
    bl_label = "Select by Type"
    bl_description = "Select all visible objects of this type"
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.type == self.object_type and is_visible_in_viewport(context, obj):
                obj.select_set(True)
        return {'FINISHED'}


# --- Operators: Lock Type Selection ---

class VIS_OT_lock_type(bpy.types.Operator):
    bl_idname = "vis.lock_type"
    bl_label = "Toggle Selection for Type"
    bl_description = ("Lock/unlock picking objects of this type in the viewport "
                      "(locked objects cannot be clicked or boxed)")
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()

    def execute(self, context):
        locked = is_type_select_disabled(self.object_type)
        for obj in bpy.data.objects:
            if obj.type == self.object_type:
                obj.hide_select = not locked
        return {'FINISHED'}


# --- Operators: Toggle Render (Type / Collection) ---

class VIS_OT_toggle_render(bpy.types.Operator):
    bl_idname = "vis.toggle_render"
    bl_label = "Toggle Render Visibility"
    bl_description = ("Exclude/restore this group in renders (camera icon). "
                      "Viewport visibility is not affected")
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty(default="")
    collection_name: bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if self.collection_name:
            collection = bpy.data.collections.get(self.collection_name)
            if not collection:
                self.report({'WARNING'}, f"Collection '{self.collection_name}' not found")
                return {'CANCELLED'}
            # тот же канал, что у камеры в аутлайнере: compose с object-level hide_render
            collection.hide_render = not collection.hide_render
            return {'FINISHED'}

        hidden = is_type_render_hidden(self.object_type)
        for obj in bpy.data.objects:
            if obj.type == self.object_type:
                obj.hide_render = not hidden
        return {'FINISHED'}


# --- Operators: Toggle Name ---

class VIS_OT_toggle_name(bpy.types.Operator):
    bl_idname = "vis.toggle_name"
    bl_label = "Toggle by Name"
    bl_description = "Hide/show all objects whose name contains the pattern (case-insensitive)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pattern = context.scene.vis_name_pattern
        if not pattern:
            self.report({'WARNING'}, "Pattern is empty")
            return {'CANCELLED'}

        all_hidden = True
        for obj in bpy.data.objects:
            if pattern.lower() in obj.name.lower() and not obj.hide_viewport:
                all_hidden = False
                break

        for obj in bpy.data.objects:
            if pattern.lower() in obj.name.lower():
                obj.hide_viewport = not all_hidden
                obj.hide_render = not all_hidden
        return {'FINISHED'}


# --- Operators: Select Name ---

class VIS_OT_select_name(bpy.types.Operator):
    bl_idname = "vis.select_name"
    bl_label = "Select by Name"
    bl_description = "Select all visible objects whose name contains the pattern"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pattern = context.scene.vis_name_pattern
        if not pattern:
            self.report({'WARNING'}, "Pattern is empty")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if pattern.lower() in obj.name.lower() and is_visible_in_viewport(context, obj):
                obj.select_set(True)
        return {'FINISHED'}


# --- Operators: Toggle Collection ---

class VIS_OT_toggle_collection(bpy.types.Operator):
    bl_idname = "vis.toggle_collection"
    bl_label = "Toggle Collection Visibility"
    bl_description = ("Hide/show this collection in the current view layer — the same "
                      "channel as the eye icon in the outliner, so object-level hides "
                      "are preserved. Shift+Click: solo — hide everything else")
    bl_options = {'REGISTER', 'UNDO'}

    collection_name: bpy.props.StringProperty()
    solo: bpy.props.BoolProperty(
        name="Solo",
        description="Hide everything except this collection",
        default=False,
    )

    def invoke(self, context, event):
        self.solo = event.shift
        return self.execute(context)

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if not collection:
            self.report({'WARNING'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}

        if self.solo:
            lc = get_layer_collection(context, collection)
            if lc is not None:
                lc.hide_viewport = False
            for obj in bpy.data.objects:
                want = obj.name in collection.objects
                obj.hide_viewport = not want
                obj.hide_render = not want
            self.report({'INFO'}, f"Solo '{collection.name}': everything else hidden")
            return {'FINISHED'}

        lc = get_layer_collection(context, collection)
        if lc is None:
            self.report({'WARNING'},
                        f"Collection '{collection.name}' is not in the current view layer")
            return {'CANCELLED'}
        lc.hide_viewport = not lc.hide_viewport
        return {'FINISHED'}


# --- Operators: Select Collection ---

class VIS_OT_select_collection(bpy.types.Operator):
    bl_idname = "vis.select_collection"
    bl_label = "Select Collection Objects"
    bl_description = "Select all visible objects of this collection"
    bl_options = {'REGISTER', 'UNDO'}

    collection_name: bpy.props.StringProperty()

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if not collection:
            self.report({'WARNING'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in collection.objects:
            if is_visible_in_viewport(context, obj):
                obj.select_set(True)
        return {'FINISHED'}


# --- Operators: By Modifier ---

class VIS_OT_select_mods(bpy.types.Operator):
    bl_idname = "vis.select_mods"
    bl_label = "Select Objects with Modifier"
    bl_description = ("Select all objects in the current scope that have this modifier "
                      "(visible objects only)")
    bl_options = {'REGISTER', 'UNDO'}

    match_key: bpy.props.StringProperty()
    match_by: bpy.props.StringProperty(default='NAME')
    match_scope: bpy.props.StringProperty(default='SCENE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in iter_scope_objects(context, self.match_scope):
            for mod in obj.modifiers:
                if (self.match_by == 'NAME' and mod.name == self.match_key) or \
                   (self.match_by == 'TYPE' and mod.type == self.match_key):
                    if is_visible_in_viewport(context, obj):
                        obj.select_set(True)
                        count += 1
                    break
        self.report({'INFO'}, f"Selected {count} object(s)")
        return {'FINISHED'}


class VIS_OT_select_mod_diffs(bpy.types.Operator):
    bl_idname = "vis.select_mod_diffs"
    bl_label = "Select Objects with Different Settings"
    bl_description = ("Select the objects whose modifier settings differ from "
                      "the majority of the group")
    bl_options = {'REGISTER', 'UNDO'}

    match_key: bpy.props.StringProperty()
    match_by: bpy.props.StringProperty(default='NAME')
    match_scope: bpy.props.StringProperty(default='SCENE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        fps = []
        for obj in iter_scope_objects(context, self.match_scope):
            if obj.library is not None:
                continue
            for mod in obj.modifiers:
                if (self.match_by == 'NAME' and mod.name == self.match_key) or \
                   (self.match_by == 'TYPE' and mod.type == self.match_key):
                    fps.append((obj, mod_fingerprint(mod)))
                    break

        if not fps:
            self.report({'WARNING'}, "No objects with this modifier")
            return {'CANCELLED'}

        common = Counter(f for _, f in fps).most_common(1)[0][0]
        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj, f in fps:
            if f != common and is_visible_in_viewport(context, obj):
                obj.select_set(True)
                count += 1
        self.report({'INFO'}, f"Selected {count} object(s) with different settings")
        return {'FINISHED'}


class VIS_OT_apply_mod(bpy.types.Operator):
    bl_idname = "vis.apply_mod"
    bl_label = "Apply Modifier on All Matched Objects"
    bl_description = ("Apply this modifier on every object that has it. "
                      "If it is not first in a stack, modifiers above it are baked "
                      "top-down first, so the result stays exactly the same")
    bl_options = {'REGISTER', 'UNDO'}

    match_key: bpy.props.StringProperty()
    match_by: bpy.props.StringProperty(default='NAME')
    match_scope: bpy.props.StringProperty(default='SCENE')
    make_single_user: bpy.props.BoolProperty(
        name="Make Single-User",
        description="Copy shared mesh data before apply "
                    "(required for linked duplicates, e.g. Alt+D copies)",
        default=True,
    )
    confirm: bpy.props.BoolProperty(
        name="Confirm",
        description="Ask for confirmation when modifiers above the target must be baked",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def target_display(self):
        if self.match_by == 'NAME':
            return self.match_key
        return self.match_key.replace('_', ' ').title()

    def build_plan(self, context):
        """Plan as [(obj, [modifier names from stack top down to target])],
        plus total count of modifiers above targets. Library-linked objects
        are skipped. Applying the chain top-down preserves the exact result:
        each modifier is first in the stack at the moment of its apply."""
        plan = []
        above = 0
        for obj in iter_scope_objects(context, self.match_scope):
            if obj.library is not None:
                continue
            for i, mod in enumerate(obj.modifiers):
                if (self.match_by == 'NAME' and mod.name == self.match_key) or \
                   (self.match_by == 'TYPE' and mod.type == self.match_key):
                    plan.append((obj, [m.name for m in obj.modifiers[:i + 1]]))
                    above += i
                    break
        return plan, above

    def draw(self, context):
        layout = self.layout
        for line in getattr(self, "_dialog_lines", []):
            layout.label(text=line)
        layout.separator()
        layout.prop(self, "make_single_user")

    def invoke(self, context, event):
        plan, above = self.build_plan(context)
        if not plan:
            self.report({'WARNING'}, "No objects with this modifier")
            return {'CANCELLED'}
        if above == 0 or not self.confirm:
            return self.execute(context)

        above_summary = {}
        for obj, chain in plan:
            for name in chain[:-1]:
                above_summary[name] = above_summary.get(name, 0) + 1
        detail = ", ".join(f"{k} ({v})" for k, v in above_summary.items())
        self._dialog_lines = [
            f"Apply '{self.target_display()}' on {len(plan)} object(s)?",
            f"Baked first (top-down): {detail}",
        ]
        try:
            return context.window_manager.invoke_props_dialog(self, confirm_text="Apply")
        except TypeError:
            return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        plan, above = self.build_plan(context)
        if not plan:
            self.report({'WARNING'}, "No objects with this modifier")
            return {'CANCELLED'}

        applied = 0
        baked = 0
        skipped = []
        for obj, chain in plan:
            try:
                if self.make_single_user and obj.data and obj.data.users > 1:
                    obj.data = obj.data.copy()
                for name in chain:
                    if obj.modifiers.get(name) is None:
                        raise RuntimeError(name)
                    with context.temp_override(object=obj, active_object=obj):
                        bpy.ops.object.modifier_apply(modifier=name)
                applied += 1
                baked += len(chain) - 1
            except RuntimeError:
                skipped.append(obj.name)

        if skipped:
            names = ', '.join(skipped[:5]) + ('...' if len(skipped) > 5 else '')
            self.report({'WARNING'},
                        f"Applied on {applied}, skipped {len(skipped)}: {names}")
        elif baked:
            self.report({'INFO'},
                        f"Applied on {applied} object(s) (baked {baked} above target)")
        else:
            self.report({'INFO'}, f"Applied on {applied} object(s)")
        return {'FINISHED'}


class VIS_OT_remove_mod(bpy.types.Operator):
    bl_idname = "vis.remove_mod"
    bl_label = "Remove Modifier from All Matched Objects"
    bl_description = ("Remove this modifier from every matched object in the current scope. "
                      "Library-linked objects are skipped")
    bl_options = {'REGISTER', 'UNDO'}

    match_key: bpy.props.StringProperty()
    match_by: bpy.props.StringProperty(default='NAME')
    match_scope: bpy.props.StringProperty(default='SCENE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        count = 0
        for obj in iter_scope_objects(context, self.match_scope):
            if obj.library is not None:
                continue
            for mod in list(obj.modifiers):
                if (self.match_by == 'NAME' and mod.name == self.match_key) or \
                   (self.match_by == 'TYPE' and mod.type == self.match_key):
                    obj.modifiers.remove(mod)
                    count += 1
        self.report({'INFO'}, f"Removed {count} modifier(s)")
        return {'FINISHED'}


class VIS_OT_remove_disabled(bpy.types.Operator):
    bl_idname = "vis.remove_disabled"
    bl_label = "Remove Disabled Modifiers"
    bl_description = ("Remove every modifier that is disabled in the viewport "
                      "(monitor off in the stack) across the current scope. "
                      "Library-linked objects are skipped")
    bl_options = {'REGISTER', 'UNDO'}

    match_scope: bpy.props.StringProperty(default='SCENE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        count = 0
        for obj in iter_scope_objects(context, self.match_scope):
            if obj.library is not None:
                continue
            for mod in list(obj.modifiers):
                if not mod.show_viewport:
                    obj.modifiers.remove(mod)
                    count += 1
        self.report({'INFO'}, f"Removed {count} disabled modifier(s)")
        return {'FINISHED'}


# --- Registration ---

classes = [
    VIS_PT_panel,
    VIS_PT_type,
    VIS_PT_name,
    VIS_PT_collections,
    VIS_PT_modifiers,
    VIS_OT_toggle_type,
    VIS_OT_select_type,
    VIS_OT_lock_type,
    VIS_OT_toggle_render,
    VIS_OT_toggle_name,
    VIS_OT_select_name,
    VIS_OT_toggle_collection,
    VIS_OT_select_collection,
    VIS_OT_select_mods,
    VIS_OT_select_mod_diffs,
    VIS_OT_apply_mod,
    VIS_OT_remove_mod,
    VIS_OT_remove_disabled,
]


def register():
    bpy.types.Scene.vis_name_pattern = bpy.props.StringProperty(
        name="Name Pattern",
        description="Substring to match object names (case-insensitive)",
        default=""
    )
    bpy.types.Scene.vis_mod_scope = bpy.props.EnumProperty(
        name="Scope",
        description="Which objects the By Modifier section scans and operates on",
        items=[
            ('SCENE', "Scene", "All objects in the scene"),
            ('SELECTED', "Selected", "Only selected objects"),
        ],
        default='SCENE',
    )
    bpy.types.Scene.vis_mod_show_diffs = bpy.props.BoolProperty(
        name="Show Setting Diffs",
        description="Compare modifier settings across the scope and show groups "
                    "where some objects differ from the majority",
        default=False,
    )
    bpy.types.Scene.vis_mod_mode = bpy.props.EnumProperty(
        name="Group By",
        description="How to group modifiers in the By Modifier section",
        items=[
            ('NAME', "Name", "Group modifiers by exact name"),
            ('TYPE', "Type", "Group modifiers by type"),
        ],
        default='NAME',
    )
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vis_name_pattern
    del bpy.types.Scene.vis_mod_mode
    del bpy.types.Scene.vis_mod_scope
    del bpy.types.Scene.vis_mod_show_diffs


if __name__ == "__main__":
    register()
