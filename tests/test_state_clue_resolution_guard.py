import unittest

from builder.state_manager import filter_supported_clue_resolutions


class ActiveClueResolutionTests(unittest.TestCase):
    def setUp(self):
        self.warning = (
            "A small, red warning light on the primary environmental controls "
            "flickered to an angry amber."
        )
        self.hitch = (
            "The low hum of life support systems hitched sharply, dipping in pitch "
            "before settling back into a thinner sound."
        )
        self.active_clues = [self.warning, self.hitch]

    def test_unmentioned_clues_are_not_removed(self):
        completed = (
            "Daniel identified isotopic markers in the input gas composition that "
            "match silicate particulates processed during regolith sample refinement."
        )
        self.assertEqual(
            filter_supported_clue_resolutions(
                self.active_clues, self.active_clues, completed
            ),
            [],
        )

    def test_merely_repeating_a_clue_does_not_resolve_it(self):
        completed = (
            "The red warning light still flickered amber while the life-support hum "
            "hitched again."
        )
        self.assertEqual(
            filter_supported_clue_resolutions(
                self.active_clues, self.active_clues, completed
            ),
            [],
        )

    def test_clear_resolution_with_overlapping_evidence_is_allowed(self):
        completed = (
            "The amber warning light on the environmental controls was a false alarm "
            "after the sensor check showed no actual fault."
        )
        self.assertEqual(
            filter_supported_clue_resolutions(
                self.active_clues, [self.warning, "A clue that never existed"], completed
            ),
            [self.warning],
        )

    def test_unknown_clues_cannot_be_removed(self):
        self.assertEqual(
            filter_supported_clue_resolutions(
                self.active_clues,
                ["An unknown radio signal came from an alien ship."],
                "The alien ship was ruled out.",
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
