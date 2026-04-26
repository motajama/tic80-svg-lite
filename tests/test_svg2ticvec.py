import tempfile
import unittest
from pathlib import Path

import svg2ticvec


class Svg2TicVecTests(unittest.TestCase):
    def write_svg(self, markup: str) -> str:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False)
        with tmp:
            tmp.write(markup)
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def assert_commands_almost_equal(self, actual, expected, places=7):
        self.assertEqual(len(actual), len(expected))
        for actual_cmd, expected_cmd in zip(actual, expected):
            self.assertEqual(actual_cmd[0], expected_cmd[0])
            self.assertEqual(len(actual_cmd), len(expected_cmd))
            for actual_value, expected_value in zip(actual_cmd[1:], expected_cmd[1:]):
                if isinstance(expected_value, float):
                    self.assertAlmostEqual(actual_value, expected_value, places=places)
                else:
                    self.assertEqual(actual_value, expected_value)

    def test_house_example_conversion(self):
        cmds = svg2ticvec.convert("examples/house.svg")
        self.assertEqual(
            cmds,
            [
                ("c", 12),
                ("c", "roof"),
                ("p", 2.0, 12.0, 12.0, 3.0, 22.0, 12.0),
                ("w", 1.5),
                ("m", 2.0, 12.0),
                ("l", 12.0, 3.0),
                ("l", 22.0, 12.0),
                ("z",),
                ("w", 1.0),
                ("c", "wall"),
                ("b", 5.0, 12.0, 14.0, 9.0),
                ("w", 1.5),
                ("r", 5.0, 12.0, 14.0, 9.0),
                ("w", 1.0),
                ("c", "door"),
                ("b", 10.0, 15.0, 4.0, 6.0),
                ("c", "window"),
                ("f", 17.0, 16.0, 1.0),
                ("o", 17.0, 16.0, 1.0),
            ],
        )

    def test_curve_segments_control_bezier_approximation(self):
        cmds = svg2ticvec.PathParser("M 0 0 C 2 0 2 2 4 2", curve_segments=4).parse()
        self.assertEqual(cmds[0], ("m", 0.0, 0.0))
        self.assertEqual(len([cmd for cmd in cmds if cmd[0] == "l"]), 4)
        self.assertEqual(cmds[-1], ("l", 4.0, 2.0))

    def test_group_translate_is_applied_to_rect(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <g transform="translate(4,4)">
                <rect x="0" y="0" width="8" height="8" />
              </g>
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("r", 4.0, 4.0, 8.0, 8.0),
            ],
        )

    def test_element_transform_is_applied_to_path_points(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <path d="M 1 2 L 3 4" transform="translate(5,6) scale(2)" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("m", 7.0, 10.0),
                ("l", 11.0, 14.0),
            ],
        )

    def test_unsupported_smooth_path_command_is_rejected_cleanly(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <path d="M 0 0 C 4 0 4 4 8 4 S 12 8 16 4" />
            </svg>
            """
        )
        with self.assertRaisesRegex(NotImplementedError, "command S is not supported"):
            svg2ticvec.convert(path)

    def test_explicit_paint_attrs_are_used_for_basic_shapes(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="2" width="3" height="4" fill="red" stroke="none" />
              <circle cx="8" cy="9" r="2" style="fill:none;stroke:#000" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("b", 1.0, 2.0, 3.0, 4.0),
                ("o", 8.0, 9.0, 2.0),
            ],
        )

    def test_polygon_fill_emits_filled_polygon_command(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <polygon points="1,1 5,1 3,4" fill="#fff" stroke="none" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("p", 1.0, 1.0, 5.0, 1.0, 3.0, 4.0),
            ],
        )

    def test_filled_path_with_stroke_emits_fill_then_outline(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <path d="M 1 1 L 5 1 L 3 4 Z" fill="#fff" stroke="#000" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("p", 1.0, 1.0, 5.0, 1.0, 3.0, 4.0),
                ("m", 1.0, 1.0),
                ("l", 5.0, 1.0),
                ("l", 3.0, 4.0),
                ("z",),
            ],
        )

    def test_filled_transformed_rect_falls_back_to_polygon_fill(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <rect x="0" y="0" width="2" height="1" fill="#fff"
                    transform="rotate(90)" />
            </svg>
            """
        )
        self.assert_commands_almost_equal(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("p", 0.0, 0.0, 0.0, 2.0, -1.0, 2.0, -1.0, 0.0),
            ],
        )

    def test_reused_inkscape_labels_emit_symbolic_color_roles(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg"
                 xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
              <rect x="1" y="2" width="3" height="4" inkscape:label="roof" fill="#fff" />
              <circle cx="8" cy="9" r="2" inkscape:label="roof" fill="#fff" />
              <rect x="10" y="1" width="2" height="2" fill="#fff" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("c", "roof"),
                ("b", 1.0, 2.0, 3.0, 4.0),
                ("f", 8.0, 9.0, 2.0),
                ("c", 12),
                ("b", 10.0, 1.0, 2.0, 2.0),
            ],
        )

    def test_to_lua_quotes_symbolic_color_roles(self):
        lua = svg2ticvec.to_lua([("c", "roof"), ("b", 1.0, 2.0, 3.0, 4.0)], "icon")
        self.assertIn('{"c", "roof"}', lua)
        self.assertIn('{"b", 1, 2, 3, 4}', lua)

    def test_stroke_width_is_emitted_for_paths(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <path d="M 1 1 L 5 1" stroke="#000" stroke-width="3" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("w", 3.0),
                ("m", 1.0, 1.0),
                ("l", 5.0, 1.0),
                ("w", 1.0),
            ],
        )

    def test_stroke_width_from_style_is_emitted_for_rect_outline(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="2" width="3" height="4"
                    style="stroke:#000;stroke-width:2.5;fill:none" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("w", 2.5),
                ("r", 1.0, 2.0, 3.0, 4.0),
                ("w", 1.0),
            ],
        )

    def test_fill_and_stroke_width_emit_both_fill_and_stroked_outline(self):
        path = self.write_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg">
              <polygon points="1,1 5,1 3,4"
                       fill="#fff" stroke="#000" stroke-width="4" />
            </svg>
            """
        )
        self.assertEqual(
            svg2ticvec.convert(path),
            [
                ("c", 12),
                ("p", 1.0, 1.0, 5.0, 1.0, 3.0, 4.0),
                ("w", 4.0),
                ("m", 1.0, 1.0),
                ("l", 5.0, 1.0),
                ("l", 3.0, 4.0),
                ("z",),
                ("w", 1.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
