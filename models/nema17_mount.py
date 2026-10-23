import cadquery as cq


def nema17_mount(
    motor_size: float = 42.3,
    hole_spacing: float = 31,
    boss_diameter: float = 22,
    screw_hole: float = 3.2,
    thickness: float = 5,
    leg_length: float = 40,
    leg_holes: float = 4.5,
) -> cq.Workplane:
    """An L-bracket for a NEMA 17 stepper motor: the motor bolts to the upright through the standard
    31 mm pattern, the foot screws down with two slots. Set 35 mm spacing and 28 mm boss for NEMA 14,
    47.14 mm and 38.1 mm for NEMA 23.
    """
    thickness = max(4, thickness)
    face = (
        cq.Workplane("XZ")
        .rect(motor_size + 2 * thickness, motor_size + thickness)
        .extrude(-thickness)
        .translate((0, 0, (motor_size + thickness) / 2))
    )
    s = hole_spacing / 2
    face = face.cut(
        cq.Workplane("XZ")
        .center(0, motor_size / 2 + thickness / 2)
        .circle(boss_diameter / 2 + 0.5)
        .extrude(-thickness * 2)
    )
    face = face.cut(
        cq.Workplane("XZ")
        .center(0, motor_size / 2 + thickness / 2)
        .pushPoints([(s, s), (-s, s), (s, -s), (-s, -s)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    foot = (
        cq.Workplane("XY")
        .box(motor_size + 2 * thickness, leg_length, thickness, centered=(True, False, False))
        .translate((0, thickness - 0.1, 0))
    )
    slots = (
        cq.Workplane("XY")
        .pushPoints([(-motor_size / 3, leg_length * 0.6), (motor_size / 3, leg_length * 0.6)])
        .slot2D(12, leg_holes, angle=90)
        .extrude(thickness)
    )
    foot = foot.cut(slots)
    web = (
        cq.Workplane("YZ")
        .polyline([(thickness, thickness), (leg_length * 0.8, thickness), (thickness, motor_size * 0.6)])
        .close()
        .extrude(thickness / 2, both=True)
    )
    x = motor_size / 2 + thickness / 2
    return face.union(foot).union(web.translate((-x, 0, 0))).union(web.translate((x, 0, 0)))
