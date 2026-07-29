from django.test import TestCase
from apps.sites.services.html_minifier import HTMLMinifier


class HTMLMinifierTests(TestCase):
    def setUp(self):
        self.minifier = HTMLMinifier()

    def test_collapses_indentation_whitespace_between_tags(self):
        html = "<div>\n    <p>Hello</p>\n    <p>World</p>\n</div>"
        result = self.minifier.minify(html)
        self.assertNotIn("\n", result)
        self.assertIn("<p>Hello</p><p>World</p>", result)

    def test_collapses_internal_whitespace_in_text(self):
        html = "<p>Hello    World\nfoo</p>"
        result = self.minifier.minify(html)
        self.assertIn("Hello World foo", result)

    def test_preserves_space_between_inline_elements(self):
        html = "<p>Hello <b>World</b></p>"
        result = self.minifier.minify(html)
        self.assertIn("Hello <b>World</b>", result)

    def test_repairs_unclosed_tag(self):
        html = "<p>Hello"
        result = self.minifier.minify(html)
        self.assertIn("<p>Hello</p>", result)

    def test_does_not_touch_script_content(self):
        html = "<script>\n  function foo() {\n    return   1;\n  }\n</script>"
        result = self.minifier.minify(html)
        self.assertIn("function foo() {\n    return   1;\n  }", result)

    def test_does_not_touch_pre_content(self):
        html = "<pre>line one\n   line two</pre>"
        result = self.minifier.minify(html)
        self.assertIn("line one\n   line two", result)

    def test_does_not_touch_textarea_content(self):
        html = "<textarea>keep    this   spacing\nand newline</textarea>"
        result = self.minifier.minify(html)
        self.assertIn("keep    this   spacing\nand newline", result)

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(self.minifier.minify(""), "")