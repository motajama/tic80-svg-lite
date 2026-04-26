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

    def test_house_example_conversion(self):
        cmds = svg2ticvec.convert("examples/house.svg")
        self.assertEqual(
            cmds,
            [
                ("c", 12),
                ("m", 2.0, 12.0),
                ("l", 12.0, 3.0),
                ("l", 22.0, 12.0),
                ("z",),
                ("r", 5.0, 12.0, 14.0, 9.0),
                ("r", 10.0, 15.0, 4.0, 6.0),
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


if __name__ == "__main__":
    unittest.main()
