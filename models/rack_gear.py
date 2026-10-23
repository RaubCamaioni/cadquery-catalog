import math
import cadquery as cq


def rack_gear(
    module: float = 2,
    teeth: int = 20,
    width: float = 10,
    base_height: float = 6,
    pressure_angle: float = 20,
    mount_holes: int = 2,
) -> cq.Workplane:
    """A straight gear rack with trapezoidal teeth that mesh with the spur_gear model of the same
    module, plus countersunk mounting holes along its base.
    """
    teeth = max(2, min(teeth, 200))
    pitch = math.pi * module
    addendum, dedendum = module, 1.25 * module
    length = teeth * pitch
    base = cq.Workplane("XY").box(length, base_height, width, centered=(False, False, False))
    tan_a = math.tan(math.radians(pressure_angle))
    half_pitch_w = pitch / 4  # half tooth thickness at the pitch line
    rack = base
    for i in range(teeth):
        cx = pitch * (i + 0.5)
        y0 = base_height - dedendum
        pts = [
            (cx - half_pitch_w - dedendum * tan_a, y0),
            (cx + half_pitch_w + dedendum * tan_a, y0),
            (cx + half_pitch_w - addendum * tan_a, base_height + addendum),
            (cx - half_pitch_w + addendum * tan_a, base_height + addendum),
        ]
        tooth = cq.Workplane("XY").polyline(pts).close().extrude(width)
        rack = rack.union(tooth)
    if mount_holes:
        n = max(1, min(mount_holes, teeth // 2))
        pts = [(length / (n + 1) * (k + 1), width / 2) for k in range(n)]
        holes = cq.Workplane("XZ").pushPoints(pts).circle(1.7).extrude(-base_height + dedendum)
        rack = rack.cut(holes)
    return rack
