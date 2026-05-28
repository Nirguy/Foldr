# Unit tests for extract_research_methods

import pytest
from app.extractor import extract_research_methods


class TestExtractResearchMethods:
    """Tests for the extract_research_methods function."""

    def test_returns_none_for_empty_text(self):
        assert extract_research_methods("") is None
        assert extract_research_methods(None) is None

    def test_returns_none_when_no_methods_heading(self):
        text = """Introduction
This paper discusses something.

Results
We found interesting things.

Discussion
We discuss the results here.
"""
        assert extract_research_methods(text) is None

    def test_extracts_methods_section(self):
        text = """Introduction
This paper discusses something.

Methods
We used a randomized controlled trial with 100 participants.
Data was collected over 6 months.

Results
We found interesting things.
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "randomized controlled trial" in result
        assert "Data was collected" in result
        # Should not include the Results section
        assert "found interesting things" not in result

    def test_extracts_methodology_section(self):
        text = """Introduction
Background info here.

Methodology
We employed qualitative analysis methods.
Interviews were conducted with 50 subjects.

Results
The findings show...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "qualitative analysis" in result
        assert "Interviews were conducted" in result

    def test_extracts_materials_and_methods(self):
        text = """Introduction
Some intro text.

Materials and Methods
Reagents were sourced from Sigma-Aldrich.
Cell cultures were maintained at 37C.

Results
Western blot analysis showed...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "Reagents were sourced" in result
        assert "Cell cultures" in result

    def test_case_insensitive_matching(self):
        text = """Introduction
Some intro.

METHODS
We used surveys and interviews.
The sample size was 200.

Results
Data analysis revealed...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "surveys and interviews" in result

    def test_case_insensitive_mixed_case(self):
        text = """Introduction
Some intro.

methods
We used surveys and interviews.

Results
Data showed...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "surveys and interviews" in result

    def test_first_match_used_when_multiple(self):
        text = """Introduction
Some intro.

Methods
First methods section content here.

Methodology
Second methods section content here.

Results
Some results.
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "First methods section" in result
        # Should not include the second methods section content
        assert "Second methods section" not in result

    def test_extracts_research_methods_heading(self):
        text = """Introduction
Some intro.

Research Methods
We applied mixed-methods research design.
Both quantitative and qualitative data were collected.

Discussion
The implications of our findings...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "mixed-methods research design" in result

    def test_extracts_experimental_design(self):
        text = """Introduction
Some intro.

Experimental Design
A double-blind placebo-controlled trial was conducted.
Participants were randomly assigned to groups.

Data Analysis
Statistical tests were performed...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "double-blind placebo-controlled" in result

    def test_extracts_research_design(self):
        text = """Introduction
Some intro.

Research Design
A longitudinal cohort study was designed.
Follow-up occurred at 6 and 12 months.

Participants
We recruited 500 adults...
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "longitudinal cohort study" in result

    def test_numbered_heading(self):
        text = """1. Introduction
Some intro.

3. Methods
We used a cross-sectional survey design.
The questionnaire was validated.

4. Results
Response rate was 78%.
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "cross-sectional survey" in result

    def test_extracts_to_end_if_no_next_heading(self):
        text = """Introduction
Some intro.

Methods
We used ethnographic observation.
Field notes were taken daily.
Analysis followed grounded theory principles.
"""
        result = extract_research_methods(text)
        assert result is not None
        assert "ethnographic observation" in result
        assert "grounded theory principles" in result
