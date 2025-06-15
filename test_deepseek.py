 rocket = create_rocket()from manim import *
import numpy as np

config.frame_size = (16, 9)
config.pixel_height = 1080
config.pixel_width = 1920
config.background_color = "#1a1a1a"

class NewtonThirdLaw3D(ThreeDScene):
    def construct(self):
        # Configure camera
        self.set_camera_orientation(phi=55*DEGREES, theta=-30*DEGREES)
        self.camera.focal_distance = 10
        
        # Animated title with depth
        title = Text("Newton's Third Law", font_size=72, gradient=(BLUE, TEAL))
        title.set_shade_in_3d(True)
        subtitle = Text("Action-Reaction Pairs", font_size=36).next_to(title, DOWN)
        subtitle.set_shade_in_3d(True)
        
        self.play(
            Write(title),
            FadeIn(subtitle, shift=DOWN),
            run_time=2
        )
        self.wait()
        self.play(
            title.animate.to_corner(UL).scale(0.6),
            subtitle.animate.to_edge(UP).scale(0.5),
            run_time=1.5
        )

        # 3D Rocket System
        rocket = self.create_rocket()
        flame = self.create_flame_particles()
        action_force, reaction_force = self.create_force_vectors(rocket)

        self.begin_ambient_camera_rotation(rate=0.1)
        self.play(
            LaggedStart(
                DrawBorderThenFill(rocket),
                Create(flame),
                lag_ratio=0.3
            ),
            run_time=3
        )
        self.play(
            GrowFromEdge(action_force, DOWN),
            GrowFromEdge(reaction_force, UP),
            run_time=2
        )
        self.wait(3)

        # Colliding Blocks Demonstration
        block1, block2 = self.create_blocks()
        collision_forces = self.create_collision_vectors(block1, block2)

        self.move_camera(phi=45*DEGREES, theta=0)
        self.play(
            FadeIn(block1, shift=LEFT*2),
            FadeIn(block2, shift=RIGHT*2),
            run_time=2
        )
        self.play(
            GrowArrow(collision_forces[0]),
            GrowArrow(collision_forces[1]),
            run_time=1.5
        )
        self.play(
            block1.animate.shift(RIGHT*2.5),
            block2.animate.shift(LEFT*2.5),
            rate_func=there_and_back,
            run_time=3
        )
        self.wait(2)

        # Interactive Skaters
        skater1, skater2 = self.create_skaters()
        push_forces = self.create_push_vectors(skater1, skater2)

        self.move_camera(phi=30*DEGREES, theta=-45*DEGREES)
        self.play(
            FadeIn(skater1, shift=LEFT*3),
            FadeIn(skater2, shift=RIGHT*3),
            run_time=2
        )
        self.play(
            GrowArrow(push_forces[0]),
            GrowArrow(push_forces[1]),
            skater1.animate.shift(LEFT*4),
            skater2.animate.shift(RIGHT*4),
            run_time=4,
            rate_func=ease_in_out_sine
        )
        self.wait(2)

        # Final composite view
        self.move_camera(phi=60*DEGREES, theta=-30*DEGREES)
        self.play(
            LaggedStart(
                rocket.animate.shift(UP*3),
                block1.animate.shift(LEFT*2),
                block2.animate.shift(RIGHT*2),
                skater1.animate.shift(UP*2),
                skater2.animate.shift(DOWN*2),
                lag_ratio=0.2
            ),
            run_time=3
        )
        self.wait(3)

    def create_rocket(self):
        # Main body with corrected parameters
        body = Cylinder(radius=0.3, height=2, fill_opacity=1, fill_color=GREY)
        cone = Cone(base_radius=0.3, height=0.8, fill_opacity=1, fill_color=RED)
        cone.next_to(body, UP, buff=0)
        
        # Fins using Box instead of Prism
        fins = VGroup(*[
            Box(width=0.8, height=0.1, depth=0.5, fill_opacity=1, fill_color=GREY)
            .rotate(angle, OUT)
            .shift(OUT*0.2 + DOWN*0.5)
            for angle in [45*DEGREES, -45*DEGREES]
        ])
        
        return VGroup(body, cone, fins).shift(DOWN*2)

    def create_flame_particles(self):
        particles = VGroup()
        for _ in range(50):
            particle = Dot3D(
                point=DOWN*3 + np.random.normal(0, 0.3, 3),
                color=np.random.choice([ORANGE, YELLOW]),
                radius=0.05
            )
            particles.add(particle)
        return particles

    def create_force_vectors(self, rocket):
        action = Arrow3D(
            start=rocket.get_bottom(),
            end=rocket.get_bottom() + 2*DOWN + OUT*0.5,
            color=RED,
            resolution=10
        )
        reaction = Arrow3D(
            start=rocket.get_top(),
            end=rocket.get_top() + 2*UP + OUT*0.5,
            color=BLUE,
            resolution=10
        )
        return action, reaction

    def create_blocks(self):
        block1 = Cube(2, fill_color=RED, fill_opacity=0.8).shift(LEFT*5)
        block2 = Cube(2, fill_color=BLUE, fill_opacity=0.8).shift(RIGHT*5)
        return block1, block2

    def create_collision_vectors(self, b1, b2):
        return VGroup(
            Arrow3D(b1.get_right(), b1.get_right()+RIGHT*2, color=RED),
            Arrow3D(b2.get_left(), b2.get_left()+LEFT*2, color=BLUE)
        )

    def create_skaters(self):
        def build_skater(color):
            body = Cylinder(radius=0.3, height=1.5, fill_color=color)
            head = Sphere(radius=0.4, color=color).shift(UP*1)
            arms = Line3D(LEFT*0.5, RIGHT*0.5).shift(UP*0.8)
            return VGroup(body, head, arms)
        
        return build_skater(RED), build_skater(BLUE)

    def create_push_vectors(self, s1, s2):
        return VGroup(
            Arrow3D(s1.get_right(), s1.get_right()+RIGHT*2, color=RED),
            Arrow3D(s2.get_left(), s2.get_left()+LEFT*2, color=BLUE)
        )