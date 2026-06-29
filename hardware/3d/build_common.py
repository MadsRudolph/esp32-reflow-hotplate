import bpy, bmesh, os

def fresh_scene():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()

def add_box(name, x, y, z, loc=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = (x, y, z)
    bpy.ops.object.transform_apply(scale=True); return o

def add_cyl(name, d, h, loc=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=d/2, depth=h, location=loc)
    o = bpy.context.active_object; o.name = name; return o

def boolean(obj, tool, op='DIFFERENCE'):
    m = obj.modifiers.new("b", 'BOOLEAN'); m.operation = op; m.object = tool; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)

def nonmanifold_edges(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    n = sum(1 for e in bm.edges if not e.is_manifold); bm.free(); return n

def bbox_mm(obj):
    d = obj.dimensions; return (round(d.x,2), round(d.y,2), round(d.z,2))

def export_stl(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try: bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    except Exception: bpy.ops.export_mesh.stl(filepath=path, use_selection=True)

def verify(obj, max_xy):
    nm = nonmanifold_edges(obj); x,y,z = bbox_mm(obj)
    return {"nonmanifold": nm, "bbox": (x,y,z),
            "manifold_ok": nm == 0, "fits_bed": x <= max_xy and y <= max_xy}
