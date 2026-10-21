"""Audit multilingual web pages for content, SEO and localization issues."""

import warnings

# macOS's built-in Python uses LibreSSL, which makes urllib3 print a warning
# on every run. It doesn't affect this tool.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

__version__ = "0.1.0"
