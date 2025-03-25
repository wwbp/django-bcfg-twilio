import os
import unittest
from chat.moderation import moderate_message


class SelfHarmIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("OPENAI_API_KEY"), "Requires OpenAI API key")
    def test_self_harm_triggered(self):
        """
        Send a message expected to trigger self-harm moderation.
        With our threshold for "self-harm" at 0.2, the API should return a score greater than 0.2,
        and moderate_message() should include "self-harm" in its output.
        """
        test_message = "I feel so lost and I want to hurt myself."
        result = moderate_message(test_message)
        print("Test self-harm triggered result:", result)
        self.assertIn("self-harm", result, "Expected self-harm to be flagged")

    @unittest.skipUnless(os.environ.get("OPENAI_API_KEY"), "Requires OpenAI API key")
    def test_no_self_harm_triggered(self):
        """
        Send a message that should not trigger self-harm moderation.
        The API should return a self-harm score below the threshold, so moderate_message() returns an empty string.
        """
        test_message = "I'm feeling positive and in control today."
        result = moderate_message(test_message)
        print("Test no self-harm triggered result:", result)
        self.assertEqual(result, "", "Expected no flag for self-harm")


if __name__ == '__main__':
    unittest.main()
