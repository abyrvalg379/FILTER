# ObjectFilter — Blender Extension
# Metadata in blender_manifest.toml

import bpy


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


def is_collection_hidden(collection):
    for obj in collection.objects:
        if not obj.hide_viewport:
            return False
    return True


def is_type_select_disabled(obj_type):
    for obj in bpy.data.objects:
        if obj.type == obj_type and not obj.hide_select:
            return False
    return True


# --- Panel ---

class VIS_PT_panel(bpy.types.Panel):
    bl_label = "FILTER"
    bl_idname = "VIS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "FILTER"

    def draw(self, context):
        layout = self.layout

        # --- By Type ---
        box = layout.box()
        box.label(text="By Type", icon='FILTER')

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

            row = box.row(align=True)
            row.label(text=f"{label} ({total})", icon=icon)

            sub = row.row(align=True)
            sub.operator("vis.toggle_type", text=f"\U0001f441 {visible}",
                         depress=visible > 0).object_type = obj_type
            sub.operator("vis.select_type", text="\u25ce").object_type = obj_type
            sub.operator("vis.lock_type", text="Lock",
                         depress=is_type_select_disabled(obj_type)).object_type = obj_type

        # --- By Name ---
        box2 = layout.box()
        box2.label(text="By Name", icon='SORTALPHA')
        box2.prop(context.scene, "vis_name_pattern", text="")

        row2 = box2.row(align=True)
        row2.operator("vis.toggle_name", text="Toggle")
        row2.operator("vis.select_name", text="Select")

        # --- Collections ---
        box3 = layout.box()
        box3.label(text="Collections", icon='OUTLINER_COLLECTION')

        for collection in bpy.data.collections:
            total = get_collection_obj_count(collection)
            if total == 0:
                continue

            visible = get_visible_count(collection=collection)

            row = box3.row(align=True)
            row.label(text=f"{collection.name} ({total})")

            sub = row.row(align=True)
            sub.operator("vis.toggle_collection", text=f"\U0001f441 {visible}",
                         depress=visible > 0).collection_name = collection.name
            sub.operator("vis.select_collection", text="\u25ce").collection_name = collection.name


# --- Operators: Toggle Type ---

class VIS_OT_toggle_type(bpy.types.Operator):
    bl_idname = "vis.toggle_type"
    bl_label = "Toggle Type Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()

    def execute(self, context):
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
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.type == self.object_type and not obj.hide_viewport:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)
        return {'FINISHED'}


# --- Operators: Lock Type Selection ---

class VIS_OT_lock_type(bpy.types.Operator):
    bl_idname = "vis.lock_type"
    bl_label = "Toggle Selection for Type"
    bl_options = {'REGISTER', 'UNDO'}

    object_type: bpy.props.StringProperty()

    def execute(self, context):
        locked = is_type_select_disabled(self.object_type)
        for obj in bpy.data.objects:
            if obj.type == self.object_type:
                obj.hide_select = not locked
        return {'FINISHED'}


# --- Operators: Toggle Name ---

class VIS_OT_toggle_name(bpy.types.Operator):
    bl_idname = "vis.toggle_name"
    bl_label = "Toggle by Name"
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
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pattern = context.scene.vis_name_pattern
        if not pattern:
            self.report({'WARNING'}, "Pattern is empty")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if pattern.lower() in obj.name.lower() and not obj.hide_viewport:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)
        return {'FINISHED'}


# --- Operators: Toggle Collection ---

class VIS_OT_toggle_collection(bpy.types.Operator):
    bl_idname = "vis.toggle_collection"
    bl_label = "Toggle Collection Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    collection_name: bpy.props.StringProperty()

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if not collection:
            self.report({'WARNING'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}

        hidden = is_collection_hidden(collection)
        for obj in collection.objects:
            obj.hide_viewport = not hidden
            obj.hide_render = not hidden
        return {'FINISHED'}


# --- Operators: Select Collection ---

class VIS_OT_select_collection(bpy.types.Operator):
    bl_idname = "vis.select_collection"
    bl_label = "Select Collection Objects"
    bl_options = {'REGISTER', 'UNDO'}

    collection_name: bpy.props.StringProperty()

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if not collection:
            self.report({'WARNING'}, f"Collection '{self.collection_name}' not found")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in collection.objects:
            if not obj.hide_viewport:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)
        return {'FINISHED'}


# --- Registration ---

classes = [
    VIS_PT_panel,
    VIS_OT_toggle_type,
    VIS_OT_select_type,
    VIS_OT_lock_type,
    VIS_OT_toggle_name,
    VIS_OT_select_name,
    VIS_OT_toggle_collection,
    VIS_OT_select_collection,
]


def register():
    bpy.types.Scene.vis_name_pattern = bpy.props.StringProperty(
        name="Name Pattern",
        description="Substring to match object names (case-insensitive)",
        default=""
    )
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vis_name_pattern


if __name__ == "__main__":
    register()
