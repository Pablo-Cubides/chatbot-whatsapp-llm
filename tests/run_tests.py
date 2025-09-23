"""
Main test runner for the WhatsApp LLM Chatbot project.
Runs all test suites and generates comprehensive reports.
"""
import pytest
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """
    Main test runner with comprehensive coverage reporting.
    """
    # Test configuration
    test_args = [
        # Test discovery
        str(Path(__file__).parent),
        
        # Verbose output
        "-v",
        "--tb=short",
        
        # Coverage configuration
        f"--cov={project_root}",
        "--cov-report=html:tests/reports/coverage_html",
        "--cov-report=xml:tests/reports/coverage.xml",
        "--cov-report=term-missing",
        
        # Exclude patterns for coverage
        "--cov-config=pyproject.toml",
        
        # JUnit XML for CI/CD
        "--junitxml=tests/reports/junit.xml",
        
        # Performance timing
        "--durations=10",
        
        # Fail on first failure (optional, remove for full test run)
        # "-x",
        
        # Show local variables in tracebacks
        "-l",
        
        # Capture settings
        "--capture=no" if "--debug" in sys.argv else "--capture=sys",
    ]
    
    logger = logging.getLogger(__name__)

    # Run specific test categories if specified
    if "--integration" in sys.argv:
        test_args.append("tests/test_integration.py")
        logger.info("🧪 Running Integration Tests Only...")
    elif "--unit" in sys.argv:
        test_args.extend([
            "tests/test_whatsapp_automation.py",
            "tests/test_chat_sessions.py"
        ])
        logger.info("🔬 Running Unit Tests Only...")
    elif "--quick" in sys.argv:
        test_args.extend([
            "tests/test_chat_sessions.py::TestChatSessions::test_save_and_load_context",
            "tests/test_whatsapp_automation.py::TestWhatsAppMessageDetection::test_message_extraction_logic"
        ])
        logger.info("⚡ Running Quick Tests Only...")
    else:
        logger.info("🚀 Running Full Test Suite...")
    
    # Create reports directory if it doesn't exist
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    logger.info(f"📊 Test reports will be saved to: {reports_dir}")
    logger.info(f"🎯 Testing codebase at: {project_root}")
    logger.info("-" * 60)
    
    # Run tests
    exit_code = pytest.main(test_args)
    
    # Print results summary
    logger.info("-" * 60)
    if exit_code == 0:
        logger.info("✅ All tests passed successfully!")
        logger.info(f"📄 Coverage report: {reports_dir / 'coverage_html' / 'index.html'}")
        logger.info(f"📊 JUnit XML: {reports_dir / 'junit.xml'}")
    else:
        logger.error("❌ Some tests failed. Check the output above for details.")
        logger.info(f"📄 Coverage report: {reports_dir / 'coverage_html' / 'index.html'}")
    
    return exit_code


def run_specific_test(test_path: str):
    """
    Run a specific test file or test function.

    Usage:
        python run_tests.py --specific tests/test_integration.py::TestManualMessagingFlow::test_complete_manual_message_flow
    """
    logging.getLogger(__name__).info(f"🎯 Running specific test: {test_path}")

    test_args = [
        test_path,
        "-v",
        "--tb=short",
        f"--cov={project_root}",
        "--cov-report=term-missing",
    ]

    return pytest.main(test_args)


def check_dependencies():
    """
    Check if all required test dependencies are available.
    """
    required_modules = ["pytest"]

    missing_modules = []

    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    logger = logging.getLogger(__name__)
    if missing_modules:
        logger.error("❌ Missing required test dependencies:")
        for module in missing_modules:
            logger.error(f"   - {module}")
        logger.info("\n📦 Install missing dependencies with:")
        logger.info("   pip install -r requirements-test.txt")
        return False

    logger.info("✅ All test dependencies are available")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("🧪 WhatsApp LLM Chatbot - Test Suite")
    logger.info("=" * 50)

    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)

    # Handle command line arguments
    if "--help" in sys.argv or "-h" in sys.argv:
        logger.info("""
Usage:
    python run_tests.py                 # Run all tests
    python run_tests.py --integration   # Run integration tests only
    python run_tests.py --unit          # Run unit tests only
    python run_tests.py --quick         # Run quick smoke tests
    python run_tests.py --specific <path> # Run specific test
    python run_tests.py --debug         # Run with debug output

Examples:
    python run_tests.py --unit
    python run_tests.py --specific tests/test_integration.py::TestManualMessagingFlow
    python run_tests.py --integration --debug

Reports:
    - HTML Coverage: tests/reports/coverage_html/index.html
    - XML Coverage: tests/reports/coverage.xml
    - JUnit XML: tests/reports/junit.xml
        """)
        sys.exit(0)

    if "--specific" in sys.argv:
        try:
            specific_index = sys.argv.index("--specific")
            test_path = sys.argv[specific_index + 1]
            exit_code = run_specific_test(test_path)
        except (IndexError, ValueError):
            logger.error("❌ Error: --specific requires a test path")
            logger.info("   Example: python run_tests.py --specific tests/test_integration.py")
            sys.exit(1)
    else:
        exit_code = main()

    sys.exit(exit_code)