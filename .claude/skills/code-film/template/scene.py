"""scene.py: builds the 3D world from timeline.py + layout.json and bakes every key.

  python scene.py [quality]      -> writes scene.blend (for inspection in Blender)
  render.py imports build() directly.

World units are metres. The UI lies flat on z = 0 (top faces of the slabs); +Y is the
top of the UI, the camera sits on the -Y side looking "up" the screen.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T

S = T.SCREEN_W / T.UI_W          # metres per UI pixel
EMIT = 2.4                       # UI emission strength when powered on


# ---------------------------------------------------------------- helpers
def px2w(px, py, z=0.0):
    return Vector(((px - T.UI_W / 2) * S, (T.UI_H / 2 - py) * S, z))


def centre(rect):
    x, y, w, h = rect
    return px2w(x + w / 2, y + h / 2)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def ease_io(u):
    u = clamp(u)
    return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2


def lerp(a, b, u):
    return a + (b - a) * u


def srgb(hexs):
    """'#E07040' -> linear RGBA (Blender colours are linear)."""
    c = [int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)


def principled(name, color, rough=0.5, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m


def box(name, size, loc, mat, parent=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    if bevel:
        m = o.modifiers.new("bevel", "BEVEL")
        m.width, m.segments, m.limit_method = bevel, 3, "ANGLE"
    bpy.ops.object.shade_smooth() if bevel else None
    if parent:
        o.parent = parent
    return o


def key(obj, f, loc=None, rot=None, scale=None):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=f)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert("rotation_euler", frame=f)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=f)


def t_of(f):
    return (f - 1) / T.FPS


# ---------------------------------------------------------------- UI slabs
def ui_material(name, img):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Base Color"].default_value = (0.004, 0.004, 0.005, 1)
    p.inputs["Roughness"].default_value = 0.35
    p.inputs["Coat Weight"].default_value = 1.0          # glassy screen: reflects the character
    p.inputs["Coat Roughness"].default_value = 0.06
    p.inputs["Emission Strength"].default_value = EMIT
    return m


def slab(name, rect, ui_mat, bezel_mat):
    x, y, w, h = rect
    g = T.PANEL_GAP_PX / 2
    x0, y0, x1, y1 = x + g, y + g, x + w - g, y + h - g
    c = centre(rect)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    corners = [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]
    vs = [bm.verts.new(px2w(px, py) - c) for px, py in corners]
    face = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, (px, py) in zip(face.loops, corners):
        loop[uv].uv = (px / T.UI_W, 1 - py / T.UI_H)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = c
    o.data.materials.append(ui_mat)
    o.data.materials.append(bezel_mat)
    sol = o.modifiers.new("thickness", "SOLIDIFY")
    sol.thickness, sol.offset = T.SLAB_T, -1
    sol.material_offset, sol.material_offset_rim = 1, 1
    bev = o.modifiers.new("bevel", "BEVEL")
    bev.width, bev.segments = 0.004, 2
    return o


# ---------------------------------------------------------------- character
def make_character():
    orange = principled("char", srgb("#E07040"), 0.45, **{"Coat Weight": 0.3, "Coat Roughness": 0.25})
    black = principled("eyes", srgb("#111114"), 0.2)
    root = bpy.data.objects.new("char", None)
    bpy.context.collection.objects.link(root)
    rig = bpy.data.objects.new("char_rig", None)        # static size; root carries squash/stretch
    bpy.context.collection.objects.link(rig)
    rig.parent = root
    leg_h = 0.035
    body_h = 0.11
    box("body", (0.17, 0.12, body_h), (0, 0, leg_h + body_h / 2), orange, rig, bevel=0.012)
    for sx in (-1, 1):
        box(f"eye{sx}", (0.018, 0.01, 0.036), (sx * 0.038, -0.058, leg_h + body_h * 0.6), black, rig, bevel=0.003)
        box(f"arm{sx}", (0.032, 0.05, 0.032), (sx * 0.1, 0, leg_h + body_h * 0.45), orange, rig, bevel=0.006)
    legs = []
    for lx in (-0.06, -0.022, 0.022, 0.06):
        # leg origin at the hip so scaling z tucks it up toward the body
        bpy.ops.object.empty_add(location=(lx, 0, leg_h))
        hip = bpy.context.object
        hip.name = f"hip{lx:+.3f}"
        hip.parent = rig
        box(f"leg{lx:+.3f}", (0.022, 0.05, leg_h + 0.004), (lx, 0, leg_h / 2 - 0.002), orange, None, bevel=0.004)
        leg = bpy.context.object
        leg.parent = hip
        leg.matrix_parent_inverse = hip.matrix_world.inverted()
        legs.append(hip)
    rig.scale = (T.CHAR_SCALE,) * 3
    return root, legs


def char_motion(L):
    """Per-frame (loc, rot, scale, leg_tuck) for the character: pure function of t."""
    pts = [centre(L["targets"][T.START])] + [centre(L["targets"][tgt]) for (_, _, tgt) in T.HOPS]
    hops = [(T.b(a), T.b(b_), pts[i], pts[i + 1], tgt) for i, (a, b_, tgt) in enumerate(T.HOPS)]
    ANTIC, LAND = 0.12, 0.45

    def yaw_for(p0, p1):
        d = p1 - p0
        if d.length < 1e-4:
            return 0.0
        a = math.atan2(d.y, d.x)                      # 0 = moving +X (crab-walk, eyes to camera)
        if a > math.pi / 2: a -= math.pi              # never turn the face away
        if a < -math.pi / 2: a += math.pi
        return 0.45 * a

    def at(t):
        pos, yaw, roll, sz, tuck = pts[0].copy(), 0.0, 0.0, 1.0, 0.0
        last_land = None
        for (t0, t1, p0, p1, tgt) in hops:
            if t < t0 - ANTIC:
                break
            y = yaw_for(p0, p1)
            if t < t0:                                # anticipation squash
                v = (t - (t0 - ANTIC)) / ANTIC
                pos, yaw, sz = p0.copy(), lerp(yaw, y, smooth(v)), 1 - 0.24 * math.sin(v * math.pi / 2)
                last_land = None
                break
            if t <= t1:                               # airborne
                u = (t - t0) / (t1 - t0)
                dist = (p1 - p0).length
                H = min(T.HOP_MAX_H, T.HOP_MIN_H + T.HOP_H_PER_M * dist)
                hz = lerp(u, smooth(u), 0.35)
                pos = p0.lerp(p1, hz)
                pos.z += H * 4 * u * (1 - u)
                vz = H * 4 * (1 - 2 * u) / (t1 - t0)
                sz = 1 + min(0.22, 0.06 * abs(vz))
                if u < 0.12:                          # blend out of the anticipation squash
                    sz = lerp(0.76, sz, u / 0.12)
                yaw = y
                tuck = math.sin(math.pi * u)
                if dist > 0.8:                        # big hop = front flip
                    roll = -2 * math.pi * ease_io(u)
                last_land = None
                break
            pos, yaw, last_land = p1.copy(), y, t1
        if last_land is not None and t - last_land < LAND:   # landing: damped squash
            w = t - last_land
            sz = 1 - 0.30 * math.exp(-9 * w) * math.cos(2 * math.pi * 3.2 * w)
        if last_land is not None or t < hops[0][0] - ANTIC:   # idle breathing
            sz *= 1 + 0.015 * math.sin(2 * math.pi * t * 1.6)
        sxy = 1 / math.sqrt(sz)
        return pos, (0.0, roll, yaw), (sxy, sxy, sz), tuck

    return at


# ---------------------------------------------------------------- world, lights, camera
def world():
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, srgb("#2c170b")
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.22, srgb("#050302")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0


def area(name, loc, target, color, power, size):
    d = bpy.data.lights.new(name, "AREA")
    d.color, d.energy, d.size = color, power, size
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    o.visible_glossy = False      # area lights reflect as hard white rectangles in the glossy UI
    return o


# ---------------------------------------------------------------- build
def build(quality="preview"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    L = json.load(open(os.path.join(HERE, "layout.json")))
    sc.render.fps = T.FPS
    sc.frame_start, sc.frame_end = 1, T.FRAMES

    img = bpy.data.images.load(os.path.join(HERE, "ui", "f_0001.png"))
    img.name = "UI"

    bezel = principled("bezel", srgb("#1a1a1e"), 0.3, **{"Metallic": 0.8})
    panels = {}
    for i, pid in enumerate(T.PANELS):
        panels[pid] = slab(f"panel_{pid}", L["panels"][pid], ui_material(f"ui_{pid}", img), bezel)

    # --- power down + fall away (every panel except KEEP_PANEL)
    flick = [1.0, 0.25, 0.9, 0.05, 0.6, 0.0]
    falling = [p for p in T.PANELS if p != T.KEEP_PANEL]
    for i, pid in enumerate(falling):
        o = panels[pid]
        inp = o.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        f0 = round(T.b(T.POWER_DOWN) * T.FPS) + 1 + 3 * i
        # flicker = hard cuts, so new keys are CONSTANT (fcurve access differs across
        # Blender versions; the preference works everywhere)
        edit = bpy.context.preferences.edit
        prev, edit.keyframe_new_interpolation_type = edit.keyframe_new_interpolation_type, "CONSTANT"
        inp.default_value = EMIT
        inp.keyframe_insert("default_value", frame=f0 - 1)
        for k, v in enumerate(flick):
            inp.default_value = EMIT * v
            inp.keyframe_insert("default_value", frame=f0 + 2 * k)
        edit.keyframe_new_interpolation_type = prev
        start = o.location.copy()
        tf = T.b(T.FALL_START) + i * T.b(T.FALL_STAGGER)
        # deterministic per-panel tumble
        rx = (0.9 if start.y > 0 else -0.9) * (0.6 + 0.4 * ((i * 37) % 7) / 7)
        rz = 0.35 * (1 if i % 2 else -1)
        for f in range(1, T.FRAMES + 1):
            tau = t_of(f) - tf
            if tau <= 0:
                if f == 1 or abs(tau) < 1.0 / T.FPS:
                    key(o, f, loc=start, rot=(0, 0, 0))
                continue
            u = tau / T.b(T.FALL_DUR)
            drop = 0.5 * 9.81 * 0.45 * tau * tau
            key(o, f, loc=start + Vector((0, 0, -drop)), rot=(rx * smooth(u * 1.5), 0, rz * smooth(u)))

    # --- character
    root, legs = make_character()
    at = char_motion(L)
    track = []
    for f in range(1, T.FRAMES + 1):
        pos, rot, scl, tuck = at(t_of(f))
        key(root, f, loc=pos, rot=rot, scale=scl)
        for h in legs:
            key(h, f, scale=(1, 1, 1 - 0.55 * tuck))
        track.append(pos.copy())

    # --- camera: follows a smoothed, slightly look-ahead version of the character
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 50
    cam_d.dof.use_dof = True
    cam_d.dof.aperture_fstop = 2.0
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    aim = bpy.data.objects.new("aim", None)
    sc.collection.objects.link(aim)
    focus = bpy.data.objects.new("focus", None)
    sc.collection.objects.link(focus)
    cam_d.dof.focus_object = focus
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"

    LOOK = round(0.25 * T.FPS)
    sm, k = track[0].copy(), 1 - math.exp(-1 / (0.30 * T.FPS))   # 0.30 s lag, cancelled by look-ahead
    comp_c = centre(L["panels"][T.KEEP_PANEL])
    end0, end1 = T.b(T.FALL_START) - 0.3, T.b(T.FALL_START) + 2.2
    for f in range(1, T.FRAMES + 1):
        t = t_of(f)
        ahead = track[min(len(track) - 1, f - 1 + LOOK)]
        flat = Vector((ahead.x, ahead.y, 0.6 * track[f - 1].z))   # partial height follow, smoothed
        sm = sm.lerp(flat, k)
        intro = 1 - ease_io(t / 2.2)          # slow opening push-in
        tgt = sm + Vector((0, 0, 0.07))
        pos = tgt + Vector((-0.30, -1.45, 0.78)) * (1 + 0.9 * intro) + Vector((0, 0, 0.5 * intro))
        e = ease_io((t - end0) / (end1 - end0))
        tgt = tgt.lerp(comp_c + Vector((-0.12, -0.08, 0)), e)
        pos = pos.lerp(comp_c + Vector((0, -2.35, 2.55)), e)
        key(cam, f, loc=pos)
        key(aim, f, loc=tgt)
        key(focus, f, loc=track[f - 1] + Vector((0, 0, 0.07)) if e < 0.5 else comp_c)
        cam_d.dof.aperture_fstop = lerp(2.0, 5.6, e)
        cam_d.dof.keyframe_insert("aperture_fstop", frame=f)

    # --- lights
    area("key", (-1.8, 2.2, 1.6), (0, 0.6, 0), (1.0, 0.58, 0.32), 260, 1.6)
    area("fill", (1.6, -2.6, 1.8), (0, 0, 0), (0.62, 0.72, 1.0), 45, 2.5)
    area("top", (0, 0.5, 3.0), (0, 0.5, 0), (1.0, 0.8, 0.6), 30, 3.0)
    world()

    # --- render settings
    W, H, spp, _ = T.QUALITY[quality]
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.use_persistent_data = True
    r.image_settings.file_format = "PNG"
    cy = sc.cycles
    cy.device = "GPU" if setup_gpu() else "CPU"
    cy.samples = spp
    cy.use_adaptive_sampling = True
    cy.use_denoising = True
    cy.max_bounces, cy.caustics_reflective, cy.caustics_refractive = 6, False, False
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    return sc


def screen_track(sc, path):
    """Character position in camera space for every frame -> json, for check.py.
    x, y in 0..1 (0,0 = bottom-left of the frame), z = distance in front of the camera,
    then the camera's world position (to catch camera pops)."""
    from bpy_extras.object_utils import world_to_camera_view
    root = bpy.data.objects["char"]
    out = []
    for f in range(1, T.FRAMES + 1):
        sc.frame_set(f)
        c = root.matrix_world @ Vector((0, 0, 0.06))
        v = world_to_camera_view(sc, sc.camera, c)
        cam = sc.camera.matrix_world.translation
        out.append([f, round(v.x, 4), round(v.y, 4), round(v.z, 4), *[round(k, 5) for k in cam]])
    sc.frame_set(1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"))


def setup_gpu():
    """Use any GPU Cycles can see (OPTIX > CUDA > HIP > METAL > ONEAPI). CPU otherwise."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except Exception:
            continue
        devs = [d for d in prefs.devices if d.type == kind]
        if devs:
            for d in prefs.devices:
                d.use = d.type == kind
            print("GPU:", [d.name for d in devs])
            return True
    print("GPU: none, rendering on CPU")
    return False


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    q = argv[0] if argv and argv[0] in T.QUALITY else "preview"
    build(q)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "scene.blend"))
    print("saved scene.blend")
