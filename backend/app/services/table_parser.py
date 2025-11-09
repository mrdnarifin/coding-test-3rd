from typing import List, Dict, Any
from datetime import datetime
from app.models.transaction import CapitalCall, Distribution, Adjustment
from sqlalchemy.orm import Session
import re

class TableParser:
    """
    Parse and classify tables extracted from PDF by DocumentProcessor
    Handles:
    - Table classification: capital_calls, distributions, adjustments
    - Row parsing and mapping to SQL models
    - Data validation and cleaning
    """

    def __init__(self, db: Session):
        self.db = db

    def parse_table(self, fund_id: int, table: Dict[str, Any]) -> int:
        """
        Parse a single table and save rows to the database.
        
        Args:
            fund_id: Fund ID for foreign key
            table: Dict containing 'headers' and 'rows'
            
        Returns:
            Number of rows successfully inserted
        """
        headers = [h.lower() for h in table.get("headers", [])]
        rows = table.get("rows", [])
        table_type = self._classify_table(headers)

        success_count = 0
        for row in rows:
            if len(row) != len(headers): 
                print(f"Skipping invalid row (wrong number of columns): {row}")
                continue

            try:
                if table_type == "capital_call":
                    # Capital Call
                    cc = CapitalCall(
                        fund_id=fund_id,
                        call_date=self._parse_date(row[0]),  # Date
                        call_type=row[1] if row[1] else "",  # Call Number
                        amount=self._parse_amount(row[2]),  # Amount
                        description=row[3] if len(row) > 3 else ""  # Description
                    )
                    self.db.add(cc)

                elif table_type == "distribution":
                    # Distribution
                    dist = Distribution(
                        fund_id=fund_id,
                        distribution_date=self._parse_date(row[0]),  # Date
                        distribution_type=row[1] if row[1] else "",  # Type
                        amount=self._parse_amount(row[2]),  # Amount
                        is_recallable=self._parse_bool(row[3]),  # Recallable
                        description=row[4] if len(row) > 4 else ""  # Description
                    )
                    self.db.add(dist)

                else:  # adjustments
                    # Adjustments
                    adj = Adjustment(
                        fund_id=fund_id,
                        adjustment_date=self._parse_date(row[0]),  # Date
                        adjustment_type=row[1] if row[1] else "",  # Type
                        amount=self._parse_amount(row[2]),  # Amount
                        is_contribution_adjustment=self._parse_bool(row[3]) if len(row) > 4 else False,  # Contribution Adjustment
                        description=row[4] if len(row) > 5 else ""  # Description
                    )
                    self.db.add(adj)

                success_count += 1

            except Exception as e:
                print(f"Error parsing row: {row}, error: {e}")
                continue

        self.db.commit()
        return success_count

    def _parse_bool(self, value: str) -> bool:
        """
        Convert string 'Yes'/'No' to boolean True/False
        """
        return value.strip().lower() == "yes" if value else False

    def _classify_table(self, headers: List[str]) -> str:
        """
        Determine table type by header keywords
        Returns: 'capital_call', 'distribution', or 'adjustment'
        """
        headers_lower = [header.lower() for header in headers]
        
        if any("call number" in header for header in headers_lower):
            return "capital_call"
        elif any("type" in header for header in headers_lower) and any("amount" in header for header in headers_lower):
            if any("recallable" in header for header in headers_lower):
                return "distribution"
            return "adjustment"
        else:
            return "adjustment"


    def _parse_date(self, date_str: str) -> datetime.date:
        """
        Parse date string to datetime.date
        Returns None if invalid
        """
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _parse_amount(self, value: Any) -> float:
        """
        Convert amount to float safely
        Returns 0.0 if invalid
        """
        try:
            if isinstance(value, str):
                value = re.sub(r"[^\d.-]", "", value)
            return float(value)
        except ValueError:
            return 0.0