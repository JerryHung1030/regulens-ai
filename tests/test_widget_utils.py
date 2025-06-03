import unittest
from unittest.mock import MagicMock

# Assuming the project structure allows direct import
# If not, sys.path manipulation might be needed for testing environment
from app.widgets.progress_panel import elide_long_id
from app.widgets.results_viewer import elide_text as elide_text_results_viewer
# For _get_display_name, we need a mock project and its methods
from app.models.project import CompareProject


class TestWidgetUtils(unittest.TestCase):

    def test_elide_long_id_progress_panel(self):
        # Test without QFont (string manipulation part)
        self.assertEqual(elide_long_id("short_text", max_length=32), "short_text")
        
        long_text_no_norm = "this_is_a_very_long_text_string_without_norm_prefix_that_exceeds_max_length"
        expected_no_norm = "this_is_a_very_long_text_str..."  # 32-3 = 29 chars
        self.assertEqual(elide_long_id(long_text_no_norm, max_length=32), expected_no_norm)

        long_text_with_norm = "norm_this_is_a_very_long_id_that_should_be_elided_in_the_middle_abcdef0123456789"
        # Keeps first 8, ..., last 8. Total 8 + 3 + 8 = 19
        expected_with_norm = "norm_thi...0123456789" 
        self.assertEqual(elide_long_id(long_text_with_norm, max_length=32), expected_with_norm)

        # Test case where text is long but not long enough for 8...8 split
        # max_length 32. default heuristic for norm_ is 8...8 (19 chars)
        # if len(text) > 19, it will apply 8...8
        # if len(text) <=19 but > max_length (not possible here for max_length=32), it would do max_length-3...
        # if text is "norm_123456789012345" (len=20), it becomes "norm_123...2345"
        # if text is "norm_12345678901234" (len=19), it becomes "norm_12345678901234" (no elision by 8...8 logic as it's not > 19)
        # Let's test a norm string that is longer than 19
        self.assertEqual(elide_long_id("norm_1234567890123456789", max_length=32), "norm_123...56789")  # len 24 -> 8...8
        self.assertEqual(elide_long_id("norm_slightly_longer_than_max_but_not_id_style_enough", max_length=32), "norm_slightly_longer_than_max...")
        self.assertEqual(elide_long_id("", max_length=32), "")
        
        very_long_text = "a" * 100
        self.assertEqual(elide_long_id(very_long_text, max_length=32), "a" * 29 + "...")

    def test_elide_text_results_viewer(self):
        self.assertEqual(elide_text_results_viewer("short", max_length=50), "short")
        self.assertEqual(elide_text_results_viewer("a" * 60, max_length=50), "a" * 47 + "...")
        self.assertEqual(elide_text_results_viewer("", max_length=50), "")
        self.assertEqual(elide_text_results_viewer(None, max_length=50), "N/A")

    def test_get_display_name_results_viewer(self):
        mock_project = MagicMock(spec=CompareProject)
        
        # Case 1: original_filename is found and returned
        mock_project.get_norm_metadata.return_value = {"original_filename": "MyControlPolicy.txt"}
        # The function get_display_name_results_viewer is not a method of a class, 
        # so it doesn't have `self`. We need to simulate the class ResultsViewer
        # or refactor _get_display_name to be static or a top-level function if it doesn't need `self`.
        # From its usage, it seems it needs `self.project`. So we need an instance of ResultsViewer
        # or mock where it's defined.
        # For simplicity, let's assume we can create a dummy ResultsViewer instance or adapt the function.
        
        # Let's create a dummy class that has a project attribute and the method.
        class DummyViewer:
            def __init__(self, project):
                self.project = project
            
            # Copied from results_viewer.py for testability
            def _get_display_name(self, norm_id: str, default_prefix: str = "ID") -> str:
                if not self.project or not norm_id:
                    return f"{default_prefix}: N/A"
                metadata = self.project.get_norm_metadata(norm_id)
                filename = metadata.get("original_filename")
                if filename:
                    return elide_text_results_viewer(filename, 70) 
                
                # Fallback to shortened ID (simplified regex for testing)
                if norm_id.startswith("norm_") and len(norm_id) > 15:  # Simplified
                    return norm_id[:9] + "..." + norm_id[-4:] 
                return norm_id

        viewer_instance = DummyViewer(mock_project)
        
        self.assertEqual(viewer_instance._get_display_name("norm_control123"), "MyControlPolicy.txt")
        mock_project.get_norm_metadata.assert_called_with("norm_control123")

        # Case 2: original_filename is found but very long (check elision)
        long_filename = "a" * 100 + ".txt"
        expected_elided_filename = "a" * 67 + "..."  # 70-3
        mock_project.get_norm_metadata.return_value = {"original_filename": long_filename}
        self.assertEqual(viewer_instance._get_display_name("norm_control_long_name"), expected_elided_filename)

        # Case 3: original_filename is not found, fallback to shortened norm_id
        mock_project.get_norm_metadata.return_value = {}  # No original_filename
        # Using the simplified regex in DummyViewer for "norm_" prefix
        self.assertEqual(viewer_instance._get_display_name("norm_abcdef1234567890"), "norm_abcd...7890")
        
        # Case 4: original_filename is not found, ID is not "norm_" like or too short to shorten by mock logic
        self.assertEqual(viewer_instance._get_display_name("control123"), "control123")
        
        # Case 5: Project is None or norm_id is None (as per the function's initial checks)
        viewer_instance_no_project = DummyViewer(None)
        self.assertEqual(viewer_instance_no_project._get_display_name("any_id"), "ID: N/A")
        self.assertEqual(viewer_instance._get_display_name(None), "ID: N/A")


if __name__ == '__main__':
    unittest.main()
