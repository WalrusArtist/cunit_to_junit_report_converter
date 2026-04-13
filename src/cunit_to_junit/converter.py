# Copyright (c) 2026 Kardo Marof. All rights reserved.
#
# This source code is licensed under the AGPL-3.0 license found in the
# LICENSE file in the root directory of this source tree.

"""Module for converting CUnit XML format to JUnit XML format."""

import logging
from pathlib import Path
from typing import Iterator, Optional

from junitparser import JUnitXml, Failure
from junitparser.xunit2 import TestCase as JUnitTestCase, TestSuite as JUnitTestSuite
from lxml import etree as ET
from lxml import objectify

logger = logging.getLogger(__name__)


def removeNamespace(tag: str) -> str:
    """Remove XML namespace from tag."""
    if '}' in tag:
        newtag = tag.split('}', 1)[1]
        return newtag
    else:
        return tag


def compareTag(tag: str, expected: str) -> bool:
    """Compare XML tag with expected value, ignoring namespace."""
    got = removeNamespace(tag)
    return got == expected


def _normalized_text(value: Optional[str]) -> str:
    """Normalize XML text content for values that may include extra whitespace."""
    if value is None:
        return ""
    return " ".join(value.split())


def _element_text(element: Optional[ET._Element]) -> str:
    """Return normalized text content for an element including nested children."""
    if element is None:
        return ""
    return _normalized_text(" ".join(text for text in element.itertext() if text and text.strip()))


def _summary_value(element: Optional[ET._Element]) -> int:
    """Convert summary values to integers while handling not-applicable markers."""
    value = _element_text(element)
    if value.lower() in {"- na -", "n/a"}:
        return 0
    return int(value) if value else 0


def _iter_test_records(root: ET._Element) -> Iterator[tuple[ET._Element, str]]:
    """Yield test result elements and their containing suite name."""
    for result_listing in root.findall(".//{*}CUNIT_RESULT_LISTING"):
        for suite in result_listing.findall(".//{*}CUNIT_RUN_SUITE"):
            suite_result = None
            for child in suite:
                if (
                    compareTag(child.tag, "CUNIT_RUN_SUITE_SUCCESS")
                    or compareTag(child.tag, "CUNIT_RUN_SUITE_FAILURE")
                ):
                    suite_result = child
                    break

            if suite_result is None:
                continue

            suite_name = _element_text(suite_result.find("./{*}SUITE_NAME")) or "UnknownSuite"
            for test_record in suite_result.findall("./{*}CUNIT_RUN_TEST_RECORD"):
                for result in test_record:
                    tag_name = removeNamespace(result.tag)
                    if tag_name in {"CUNIT_RUN_TEST_SUCCESS", "CUNIT_RUN_TEST_FAILURE"}:
                        yield result, suite_name


def _parse_cunit_summary(root: ET._Element) -> tuple[int, int]:
    """Parse CUnit summary to extract test counts."""
    total_tests = 0
    total_failures = 0
    
    for child in root:
        if compareTag(child.tag, "CUNIT_RUN_SUMMARY"):
            for record in child:
                if compareTag(record.tag, "CUNIT_RUN_SUMMARY_RECORD"):
                    type_elem = record.find(".//{*}TYPE")
                    if type_elem is not None and "Test Cases" in _element_text(type_elem):
                        total_elem = record.find(".//{*}TOTAL")
                        failed_elem = record.find(".//{*}FAILED")
                        total_tests = _summary_value(total_elem)
                        total_failures = _summary_value(failed_elem)
    
    return total_tests, total_failures


def _create_testcase_element(
    test_name: Optional[str],
    classname: str,
    file_name_elem: Optional[ET._Element],
    line_number_elem: Optional[ET._Element],
    condition_elem: Optional[ET._Element],
) -> JUnitTestCase:
    """Create a testcase element and add failure information if applicable."""
    testcase = JUnitTestCase(
        name=test_name.strip() if test_name else "UnknownTest",
        classname=classname,
        time=0.0,
    )

    # Check if test failed
    if file_name_elem is not None and line_number_elem is not None:
        file_name = _element_text(file_name_elem) or "unknown"
        line_number = _element_text(line_number_elem) or "0"
        condition = _element_text(condition_elem) or "Assertion failed"
        failure = Failure(condition.strip(), "AssertionError")
        failure.text = f"{file_name}:{line_number}: {condition}"
        testcase.result = [failure]

    return testcase


def _process_test_record(
    result: ET._Element, testsuite: JUnitTestSuite, suite_name: str, current_suite_name: str
) -> None:
    """Process a single test record and add it to the testsuite."""
    test_name_elem = result.find("./{*}TEST_NAME")
    file_name_elem = result.find(".//{*}FILE_NAME")
    line_number_elem = result.find(".//{*}LINE_NUMBER")
    condition_elem = result.find(".//{*}CONDITION")
    test_name = _element_text(test_name_elem) or "UnknownTest"
    classname = current_suite_name.strip() if current_suite_name else suite_name

    testcase = _create_testcase_element(
        test_name,
        classname,
        file_name_elem,
        line_number_elem,
        condition_elem,
    )

    requirements = [_element_text(req) for req in result.findall(".//{*}REQUIREMENTS/{*}REQ") if _element_text(req)]
    description = _element_text(result.find(".//{*}DESCRIPTION"))
    comment = _element_text(result.find(".//{*}COMMENT"))

    if requirements:
        testcase.add_property("requirements", ", ".join(requirements))
    if description:
        testcase.add_property("description", description)
    if comment:
        testcase.add_property("comment", comment)

    testsuite.add_testcase(testcase)


def _parse_test_results(root: ET._Element, testsuite: JUnitTestSuite, suite_name: str) -> None:
    """Parse individual test results from CUnit XML and add them to testsuite."""
    for result, current_suite_name in _iter_test_records(root):
        _process_test_record(result, testsuite, suite_name, current_suite_name)


def _create_placeholder_tests(testsuite: JUnitTestSuite, total_tests: int, total_failures: int, suite_name: str) -> None:
    """Create placeholder tests if no test results were found."""
    if not any(True for _ in testsuite) and total_tests > 0:
        for i in range(total_tests):
            testcase = JUnitTestCase(name=f"test_{i+1}", classname=suite_name, time=0.0)
            if i < total_failures:
                failure = Failure("Test failed", "AssertionError")
                failure.text = "Test failed (details not available in CUnit output)"
                testcase.result = [failure]
            testsuite.add_testcase(testcase)


def cunit_to_junit(cunit_xml_path: Path, junit_xml_path: Path) -> None:
    """
    Convert CUnit XML format to JUnit XML format.
    
    Args:
        cunit_xml_path: Path to the input CUnit XML file
        junit_xml_path: Path to the output JUnit XML file
    """
    try:
        parser = ET.XMLParser(remove_blank_text=True)
        tree = objectify.parse(str(cunit_xml_path), parser=parser)
        root = tree.getroot()
        
        suite_name = cunit_xml_path.stem

        # Parse CUnit summary for counts
        total_tests, total_failures = _parse_cunit_summary(root)

        # Create JUnit testsuite
        testsuite = JUnitTestSuite(suite_name)
        testsuite.tests = total_tests
        testsuite.failures = total_failures

        # Parse individual test results from CUnit XML
        _parse_test_results(root, testsuite, suite_name)

        # If no test results were found, create placeholders
        _create_placeholder_tests(testsuite, total_tests, total_failures, suite_name)

        # Write JUnit XML
        xml = JUnitXml()
        xml.add_testsuite(testsuite)
        xml.write(str(junit_xml_path), pretty=True)
        logger.info(f"Generated JUnit XML: {junit_xml_path}")
    except Exception as e:
        logger.error(f"Failed to convert CUnit XML to JUnit XML: {e}")
        raise
