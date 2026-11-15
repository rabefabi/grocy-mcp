"""
Open Food Facts lookup tool for Grocy MCP server.

Provides tool to search nutritional data from Open Food Facts database.
Includes retry logic for transient errors and graceful fallback.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from ..utils.annotations import READ_ONLY

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

OFF_API_BASE = "https://world.openfoodfacts.org"

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 0.5  # seconds
BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


def _make_request_with_retry(
    url: str,
    params: dict | None = None,
    timeout: int = 10,
) -> tuple[httpx.Response | None, str | None]:
    """
    Make HTTP request with retry logic for transient errors.
    
    Returns:
        Tuple of (response, error_message). If successful, error_message is None.
        If all retries exhausted, response is None and error_message describes the failure.
    """
    last_error = None
    backoff = INITIAL_BACKOFF
    
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client() as c:
                r = c.get(url, params=params, timeout=timeout)
                r.raise_for_status()
                return r, None
        except Exception as e:
            last_error = e
            if not _is_retryable_error(e) or attempt == MAX_RETRIES - 1:
                break
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER
    
    # Determine error type for the response
    error_msg = str(last_error)
    if isinstance(last_error, httpx.HTTPStatusError):
        status = last_error.response.status_code
        if status in RETRYABLE_STATUS_CODES:
            return None, f"source_unavailable: Open Food Facts returned HTTP {status} after {MAX_RETRIES} retries"
    elif isinstance(last_error, httpx.TimeoutException):
        return None, f"source_unavailable: Open Food Facts timed out after {MAX_RETRIES} retries"
    elif isinstance(last_error, httpx.ConnectError):
        return None, f"source_unavailable: Could not connect to Open Food Facts after {MAX_RETRIES} retries"
    
    return None, f"error: {error_msg}"


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register Open Food Facts lookup tool."""

    @mcp.tool(annotations=READ_ONLY)
    def lookup_product_openfoodfacts(
        query: str = "", barcode: str = ""
    ) -> dict[str, Any]:
        """
        Search for product nutritional data from Open Food Facts database.

        You can search by product name or barcode. Returns up to 5 matches for
        text search, or exact match for barcode lookup.

        Args:
            query: Product name to search for (e.g., "goat cheese")
            barcode: Product barcode/EAN to look up

        Returns:
            If barcode provided: Single product result with nutritional data
            If query provided: List of up to 5 product matches
            Fields: product_name, barcode, calories (kcal/100g),
                   protein, fat, carbs (all per 100g), image_url
        """
        if barcode:
            return _lookup_by_barcode(barcode)
        elif query:
            return _search_by_query(query)
        else:
            return {"error": "Either 'query' or 'barcode' must be provided"}

    def _lookup_by_barcode(barcode: str) -> dict[str, Any]:
        """Look up a product by its barcode."""
        url = f"{OFF_API_BASE}/api/v0/product/{barcode}.json"
        response, error = _make_request_with_retry(url)
        
        if error:
            # Distinguish source_unavailable from other errors
            if error.startswith("source_unavailable"):
                return {
                    "status": "source_unavailable",
                    "barcode": barcode,
                    "message": error,
                    "fallback_guidance": "OpenFoodFacts is temporarily unavailable. You can proceed to create the product without nutritional data and update it later.",
                }
            return {
                "status": "error",
                "barcode": barcode,
                "error": error,
                "message": f"Failed to look up barcode {barcode}",
            }
        
        assert response is not None
        try:
            data = response.json()
            
            if data.get("status") == 0:
                return {
                    "status": "not_found",
                    "barcode": barcode,
                    "message": "Product not found in Open Food Facts",
                }

            product = data.get("product", {})
            return {
                "status": "found",
                "product_name": product.get("product_name", "Unknown"),
                "barcode": product.get("code", barcode),
                "calories_per_100g": product.get("nutriments", {}).get(
                    "energy-kcal_100g"
                ),
                "protein_per_100g": product.get("nutriments", {}).get(
                    "proteins_100g"
                ),
                "fat_per_100g": product.get("nutriments", {}).get("fat_100g"),
                "carbs_per_100g": product.get("nutriments", {}).get(
                    "carbohydrates_100g"
                ),
                "image_url": product.get("image_url"),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Failed to parse response for barcode {barcode}",
            }

    def _search_by_query(query: str) -> dict[str, Any]:
        """Search for products by name."""
        url = f"{OFF_API_BASE}/cgi/search.pl"
        params = {
            "search_terms": query,
            "json": 1,
            "page_size": 5,
        }
        response, error = _make_request_with_retry(url, params=params)
        
        if error:
            # Distinguish source_unavailable from other errors
            if error.startswith("source_unavailable"):
                return {
                    "status": "source_unavailable",
                    "query": query,
                    "message": error,
                    "fallback_guidance": "OpenFoodFacts is temporarily unavailable. You can proceed to create the product without nutritional data and update it later.",
                }
            return {
                "status": "error",
                "query": query,
                "error": error,
                "message": f"Failed to search for '{query}'",
            }
        
        assert response is not None
        try:
            data = response.json()
            results = data.get("products", [])
            if not results:
                return {
                    "status": "no_results",
                    "query": query,
                    "message": "No products found for this search",
                }

            matches = []
            for product in results[:5]:
                matches.append(
                    {
                        "product_name": product.get("product_name", "Unknown"),
                        "barcode": product.get("code"),
                        "calories_per_100g": product.get("nutriments", {}).get(
                            "energy-kcal_100g"
                        ),
                        "protein_per_100g": product.get("nutriments", {}).get(
                            "proteins_100g"
                        ),
                        "fat_per_100g": product.get("nutriments", {}).get(
                            "fat_100g"
                        ),
                        "carbs_per_100g": product.get("nutriments", {}).get(
                            "carbohydrates_100g"
                        ),
                        "image_url": product.get("image_url"),
                    }
                )

            return {
                "status": "found",
                "query": query,
                "count": len(matches),
                "products": matches,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": f"Failed to parse search results for '{query}'",
            }
