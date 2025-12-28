"""Tests for glob pattern overlap detection utilities."""

from __future__ import annotations

from lodestar.util.locks import (
    find_overlapping_patterns,
    globs_overlap,
    normalize_glob_pattern,
)


class TestNormalizeGlobPattern:
    """Test glob pattern normalization."""

    def test_normalize_backslashes(self):
        """Windows-style backslashes converted to forward slashes."""
        result = normalize_glob_pattern(r"src\auth\login.py")
        assert result == "src/auth/login.py"

    def test_normalize_mixed_slashes(self):
        """Mixed slashes all become forward slashes."""
        result = normalize_glob_pattern(r"src/auth\users\**")
        assert result == "src/auth/users/**"

    def test_normalize_leading_dot_slash(self):
        """Leading ./ is removed."""
        result = normalize_glob_pattern("./src/auth")
        assert result == "src/auth"

    def test_normalize_trailing_slash(self):
        """Trailing slashes are stripped."""
        result = normalize_glob_pattern("src/auth/")
        assert result == "src/auth"

    def test_normalize_empty_string(self):
        """Empty string returns empty."""
        result = normalize_glob_pattern("")
        assert result == ""

    def test_normalize_preserves_wildcards(self):
        """Wildcards are preserved."""
        result = normalize_glob_pattern("src/**/*.py")
        assert result == "src/**/*.py"

    def test_normalize_simple_path(self):
        """Simple paths pass through unchanged."""
        result = normalize_glob_pattern("src/main.py")
        assert result == "src/main.py"


class TestGlobsOverlap:
    """Test glob pattern overlap detection."""

    def test_exact_match_overlaps(self):
        """Identical patterns overlap."""
        assert globs_overlap("src/auth/**", "src/auth/**") is True

    def test_parent_contains_child(self):
        """Parent glob contains child path."""
        assert globs_overlap("src/**", "src/auth/login.py") is True

    def test_child_overlaps_parent(self):
        """Child path overlaps with parent glob (symmetric)."""
        assert globs_overlap("src/auth/login.py", "src/**") is True

    def test_sibling_directories_no_overlap(self):
        """Sibling directories don't overlap."""
        assert globs_overlap("src/auth/**", "src/api/**") is False

    def test_completely_different_paths(self):
        """Completely different paths don't overlap."""
        assert globs_overlap("src/**", "tests/**") is False

    def test_empty_pattern_no_overlap(self):
        """Empty patterns don't overlap with anything."""
        assert globs_overlap("", "src/**") is False
        assert globs_overlap("src/**", "") is False
        assert globs_overlap("", "") is False

    def test_specific_file_overlap(self):
        """Specific file paths that match."""
        assert globs_overlap("src/main.py", "src/main.py") is True
        assert globs_overlap("src/main.py", "src/other.py") is False

    def test_double_star_matches_deep_paths(self):
        """** matches multiple directory levels."""
        assert globs_overlap("src/**", "src/a/b/c/d.py") is True

    def test_single_star_single_level(self):
        """* matches only at one directory level."""
        assert globs_overlap("src/*.py", "src/main.py") is True

    def test_nested_glob_patterns(self):
        """Both patterns have globs and could match same files."""
        assert globs_overlap("src/**/*.py", "src/auth/**") is True

    def test_glob_in_different_subtrees(self):
        """Globs in different subtrees don't overlap."""
        assert globs_overlap("src/auth/**", "tests/auth/**") is False

    def test_windows_path_overlap(self):
        """Windows-style paths are normalized before comparison."""
        assert globs_overlap(r"src\auth\**", "src/auth/login.py") is True

    def test_prefix_overlap(self):
        """Patterns with overlapping prefixes."""
        assert globs_overlap("src/auth/**", "src/auth/users/**") is True

    def test_partial_name_no_overlap(self):
        """Partial directory name matches don't count as overlap."""
        assert globs_overlap("src/auth/**", "src/authorization/**") is False


class TestFindOverlappingPatterns:
    """Test finding overlapping pattern pairs."""

    def test_finds_single_overlap(self):
        """Finds a single overlap between lists."""
        overlaps = find_overlapping_patterns(["src/auth/**"], ["src/**"])
        assert len(overlaps) == 1
        assert ("src/auth/**", "src/**") in overlaps

    def test_finds_multiple_overlaps(self):
        """Finds multiple overlaps."""
        patterns1 = ["src/auth/**", "src/api/**"]
        patterns2 = ["src/**"]
        overlaps = find_overlapping_patterns(patterns1, patterns2)
        assert len(overlaps) == 2
        assert ("src/auth/**", "src/**") in overlaps
        assert ("src/api/**", "src/**") in overlaps

    def test_no_overlaps_returns_empty(self):
        """No overlaps returns empty list."""
        overlaps = find_overlapping_patterns(["src/**"], ["tests/**"])
        assert overlaps == []

    def test_empty_lists(self):
        """Empty lists return empty result."""
        assert find_overlapping_patterns([], ["src/**"]) == []
        assert find_overlapping_patterns(["src/**"], []) == []
        assert find_overlapping_patterns([], []) == []

    def test_multiple_patterns_both_sides(self):
        """Multiple patterns on both sides."""
        patterns1 = ["src/auth/**", "tests/auth/**"]
        patterns2 = ["src/**", "docs/**"]
        overlaps = find_overlapping_patterns(patterns1, patterns2)
        assert len(overlaps) == 1
        assert ("src/auth/**", "src/**") in overlaps

    def test_self_overlap(self):
        """Same pattern in both lists."""
        overlaps = find_overlapping_patterns(["src/**"], ["src/**"])
        assert len(overlaps) == 1
        assert ("src/**", "src/**") in overlaps

    def test_returns_all_matching_pairs(self):
        """Returns all matching pairs, not just first match."""
        patterns1 = ["src/**"]
        patterns2 = ["src/auth/**", "src/api/**", "src/utils/**"]
        overlaps = find_overlapping_patterns(patterns1, patterns2)
        assert len(overlaps) == 3
