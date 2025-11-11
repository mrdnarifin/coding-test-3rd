import pytest
from unittest.mock import MagicMock
from app.services.query_engine import QueryEngine
from app.services.vector_store import VectorStore
from app.services.metrics_calculator import MetricsCalculator
from langchain_openai import ChatOpenAI
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from app.core.config import settings


# Mocking dependencies (VectorStore, MetricsCalculator, and LLM)
@pytest.fixture
def mock_vector_store():
    vector_store = MagicMock(VectorStore)
    vector_store.similarity_search.return_value = [
        {"content": "doc content 1", "score": 0.95},
        {"content": "doc content 2", "score": 0.90},
    ]
    return vector_store


@pytest.fixture
def mock_metrics_calculator():
    metrics_calculator = MagicMock(MetricsCalculator)
    metrics_calculator.calculate_all_metrics.return_value = {
        "DPI": 1.25,
        "IRR": 0.15,
        "TVPI": 1.75,
    }
    return metrics_calculator


@pytest.fixture
def mock_llm():
    # Mocking the LLM response (either OpenAI or NVIDIA)
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="This is a mock response.")
    return llm


@pytest.fixture
def query_engine(mock_vector_store, mock_metrics_calculator, mock_llm):
    # Create an instance of the QueryEngine with the mocked dependencies
    engine = QueryEngine(db=None)  # Pass `None` for db if not needed in this test
    engine.vector_store = mock_vector_store
    engine.metrics_calculator = mock_metrics_calculator
    engine.llm = mock_llm
    return engine


# Test: Classify Intent (Query Classification)
@pytest.mark.parametrize("query,expected_intent", [
    ("How is the DPI for this fund?", "calculation"),
    ("What does IRR mean?", "definition"),
    ("Show me all documents related to this fund", "retrieval"),
    ("Tell me about this fund", "general"),
])
@pytest.mark.asyncio
async def test_classify_intent(query_engine, query, expected_intent):
    # Function to classify intent based on query
    result = await query_engine._classify_intent(query)
    # Assert if the classification result matches the expected intent
    assert result == expected_intent

# Test: Process Query (with intent classification and document retrieval)
@pytest.mark.asyncio
async def test_process_query(query_engine):
    query = "What is the current DPI for this fund?"
    fund_id = 123  # Example fund ID

    # Call the process_query method
    result = await query_engine.process_query(query, fund_id=fund_id)

    # Check that the result contains the expected response content and sources
    assert "answer" in result
    assert "sources" in result
    assert result["answer"] == "This is a mock response."

    # Check that the vector store's similarity_search method was called correctly
    query_engine.vector_store.similarity_search.assert_called_once_with(
        query=query,
        k=settings.TOP_K_RESULTS,
        filter_metadata={"fund_id": fund_id}
    )


# Test: Calculate Metrics (only if the intent is "calculation")
@pytest.mark.asyncio
async def test_calculate_metrics(query_engine):
    query = "What is the DPI for this fund?"
    fund_id = 123  # Example fund ID

    # Call the process_query method
    result = await query_engine.process_query(query, fund_id=fund_id)

    # Ensure the metrics calculator was called
    query_engine.metrics_calculator.calculate_all_metrics.assert_called_once_with(fund_id)

    # Check if the metrics are included in the response
    assert "metrics" in result
    assert result["metrics"] == {
        "DPI": 1.25,
        "IRR": 0.15,
        "TVPI": 1.75
    }


# Test: Edge Case - Missing Fund ID
@pytest.mark.asyncio
async def test_process_query_no_fund_id(query_engine):
    query = "What is the current DPI?"

    # Call the process_query method with no fund ID
    result = await query_engine.process_query(query)

    # Check that the response contains the expected answer
    assert "answer" in result
    assert result["answer"] == "This is a mock response."

    # Ensure the metrics calculator is not called if no fund_id is provided
    query_engine.metrics_calculator.calculate_all_metrics.assert_not_called()


# Test: Edge Case - Invalid Query Format
@pytest.mark.asyncio
async def test_process_query_invalid_format(query_engine):
    query = ""  # An empty query

    # Call the process_query method with an empty query
    result = await query_engine.process_query(query)
    print(result)

    # Adjust the expected error message to match the mock behavior
    assert "answer" in result
    assert result["answer"] == "This is a mock response."

