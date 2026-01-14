"""
Test State Manager for E2E Test Crash Recovery.

This module provides crash recovery support for E2E tests by persisting
test state to disk after each step. On test restart, it can resume from
the last completed step.

Usage:
    state_mgr = TestStateManager("test_domain_intelligence")

    # Check if resuming
    if state_mgr.has_state():
        completed = state_mgr.get_completed_steps()
        products = state_mgr.get_products_completed()
    else:
        state_mgr.save_state({"status": "RUNNING"})

    # After each step
    state_mgr.mark_step_complete("fetch_cloudflare_sites")
    state_mgr.save_state()

    # After each product
    state_mgr.add_product(product_data)
    state_mgr.mark_product_complete(product_id)
    state_mgr.save_state()
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestStateManager:
    """
    Manages test state for crash recovery.

    Persists state to JSON files with atomic writes (temp file + rename)
    to prevent data corruption on crash.
    """

    BASE_DIR = Path(__file__).parent.parent / "outputs"

    def __init__(self, test_name: str):
        """
        Initialize state manager for a specific test.

        Args:
            test_name: Unique identifier for the test run
        """
        self.test_name = test_name
        self.state_file = self.BASE_DIR / f"e2e_state_{test_name}.json"
        self._state: Dict[str, Any] = {}

        # Ensure output directory exists
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing state if available
        if self.has_state():
            self._state = self.load_state()

    def _get_default_state(self) -> Dict[str, Any]:
        """Get default state structure."""
        return {
            "test_name": self.test_name,
            "started_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "status": "RUNNING",
            "current_step": "",
            "completed_steps": [],
            "completed_products": [],
            "products": [],
            "domain_profiles": [],
            "errors": [],
            "metrics": {},
        }

    def has_state(self) -> bool:
        """Check if state file exists."""
        return self.state_file.exists()

    def load_state(self) -> Dict[str, Any]:
        """
        Load previous test state from file.

        Returns:
            State dictionary or empty dict if no state exists
        """
        if not self.state_file.exists():
            return self._get_default_state()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load state file: {e}")
            return self._get_default_state()

    def save_state(self, state: Optional[Dict[str, Any]] = None) -> None:
        """
        Save current test state to file (atomic write).

        Uses temp file + rename pattern to prevent corruption.

        Args:
            state: Optional state dict to save. If None, saves current internal state.
        """
        if state:
            self._state.update(state)

        self._state["last_updated"] = datetime.utcnow().isoformat()

        # Atomic write: write to temp file, then rename
        temp_file = self.state_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, default=str)

            # Atomic rename
            shutil.move(str(temp_file), str(self.state_file))
        except Exception as e:
            print(f"Error saving state: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def get_completed_steps(self) -> List[str]:
        """Get list of completed steps."""
        return self._state.get("completed_steps", [])

    def mark_step_complete(self, step_name: str) -> None:
        """
        Mark a step as complete.

        Args:
            step_name: Name of the completed step
        """
        if "completed_steps" not in self._state:
            self._state["completed_steps"] = []

        if step_name not in self._state["completed_steps"]:
            self._state["completed_steps"].append(step_name)

        self._state["current_step"] = step_name
        self.save_state()

    def is_step_complete(self, step_name: str) -> bool:
        """Check if a step is already complete."""
        return step_name in self._state.get("completed_steps", [])

    def get_products_completed(self) -> List[str]:
        """Get list of completed product IDs."""
        return self._state.get("completed_products", [])

    def mark_product_complete(self, product_id: str) -> None:
        """
        Mark a product as complete.

        Args:
            product_id: ID of the completed product
        """
        if "completed_products" not in self._state:
            self._state["completed_products"] = []

        if product_id not in self._state["completed_products"]:
            self._state["completed_products"].append(product_id)

        self.save_state()

    def is_product_complete(self, product_id: str) -> bool:
        """Check if a product is already complete."""
        return product_id in self._state.get("completed_products", [])

    def add_product(self, product_data: Dict[str, Any]) -> None:
        """
        Add or update a product in state.

        Args:
            product_data: Product data dictionary (must have 'id' key)
        """
        if "products" not in self._state:
            self._state["products"] = []

        # Update existing or add new
        product_id = product_data.get("id")
        existing_idx = None

        for idx, p in enumerate(self._state["products"]):
            if p.get("id") == product_id:
                existing_idx = idx
                break

        if existing_idx is not None:
            self._state["products"][existing_idx] = product_data
        else:
            self._state["products"].append(product_data)

        self.save_state()

    def add_domain_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        Add or update a domain profile in state.

        Args:
            profile_data: Domain profile dictionary (must have 'domain' key)
        """
        if "domain_profiles" not in self._state:
            self._state["domain_profiles"] = []

        # Update existing or add new
        domain = profile_data.get("domain")
        existing_idx = None

        for idx, p in enumerate(self._state["domain_profiles"]):
            if p.get("domain") == domain:
                existing_idx = idx
                break

        if existing_idx is not None:
            self._state["domain_profiles"][existing_idx] = profile_data
        else:
            self._state["domain_profiles"].append(profile_data)

        self.save_state()

    def add_error(self, error_data: Dict[str, Any]) -> None:
        """
        Add an error to state.

        Args:
            error_data: Error data dictionary
        """
        if "errors" not in self._state:
            self._state["errors"] = []

        error_data["timestamp"] = datetime.utcnow().isoformat()
        self._state["errors"].append(error_data)
        self.save_state()

    def set_status(self, status: str) -> None:
        """
        Set test status.

        Args:
            status: One of RUNNING, COMPLETED, FAILED, PARTIAL
        """
        self._state["status"] = status
        self.save_state()

    def set_current_step(self, step_name: str) -> None:
        """Set the current step being executed."""
        self._state["current_step"] = step_name
        self.save_state()

    def set_metrics(self, metrics: Dict[str, Any]) -> None:
        """Set test metrics."""
        self._state["metrics"] = metrics
        self.save_state()

    def clear_state(self) -> None:
        """Clear state file and reset internal state."""
        if self.state_file.exists():
            self.state_file.unlink()
        self._state = self._get_default_state()

    def get_state(self) -> Dict[str, Any]:
        """Get current state dictionary."""
        return self._state.copy()

    def get_products(self) -> List[Dict[str, Any]]:
        """Get list of products from state."""
        return self._state.get("products", [])

    def get_domain_profiles(self) -> List[Dict[str, Any]]:
        """Get list of domain profiles from state."""
        return self._state.get("domain_profiles", [])

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get list of errors from state."""
        return self._state.get("errors", [])
