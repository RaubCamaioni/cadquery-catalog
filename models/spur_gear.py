import math
import cadquery as cq


def _involute_tooth(module: float, teeth: int, pressure_angle: float, steps: int = 8) -> list[tuple[float, float]]:
    """Points of one tooth outline (both flanks), in the gear's XY plane, tip included."""
    pa = math.radians(pressure_angle)
    r_pitch = module * teeth / 2
    r_base = r_pitch * math.cos(pa)
    r_tip = r_pitch + module
    r_root = max(r_pitch - 1.25 * module, r_base * 0.98)
    # involute angle at the pitch circle, used to centre the tooth on the x axis
    t_pitch = math.sqrt((r_pitch / r_base) ** 2 - 1)
    inv_pitch = t_pitch - math.atan(t_pitch)
    half_tooth = math.pi / (2 * teeth) + inv_pitch
    t_max = math.sqrt((r_tip / r_base) ** 2 - 1)
    flank = []
    for i in range(steps + 1):
        t = t_max * i / steps
        r = r_base * math.sqrt(1 + t * t)
        a = t - math.atan(t)
        flank.append((r, a))
    right = [(r * math.cos(-half_tooth + a), r * math.sin(-half_tooth + a)) for r, a in flank]
    left = [(r * math.cos(half_tooth - a), r * math.sin(half_tooth - a)) for r, a in reversed(flank)]
    root_right = (r_root * math.cos(-half_tooth - 0.02), r_root * math.sin(-half_tooth - 0.02))
    root_left = (r_root * math.cos(half_tooth + 0.02), r_root * math.sin(half_tooth + 0.02))
    return [root_right, *right, *left, root_left]


def spur_gear(
    module: float = 2,
    teeth: int = 20,
    thickness: float = 8,
    bore_diameter: float = 6,
    pressure_angle: float = 20,
    hub_diameter: float = 0,
    hub_height: float = 0,
) -> cq.Workplane:
    """A straight-cut spur gear with involute teeth. Two gears mesh when their modules match;
    the centre distance is module * (teeth_a + teeth_b) / 2.
    """
    teeth = max(6, min(int(teeth), 200))
    module = max(0.5, module)
    pressure_angle = max(14.5, min(pressure_angle, 25))
    r_root = module * teeth / 2 - 1.25 * module
    gear = cq.Workplane("XY").circle(r_root + 0.05).extrude(thickness)
    tooth = cq.Workplane("XY").polyline(_involute_tooth(module, teeth, pressure_angle)).close().extrude(thickness)
    for i in range(teeth):
        gear = gear.union(tooth.rotate((0, 0, 0), (0, 0, 1), 360 * i / teeth))
    if hub_diameter > bore_diameter + 2 and hub_height > 0:
        gear = gear.union(cq.Workplane("XY").circle(hub_diameter / 2).extrude(thickness + hub_height))
    if bore_diameter > 0:
        gear = gear.cut(cq.Workplane("XY").circle(bore_diameter / 2).extrude(thickness + max(hub_height, 0)))
    return gear
