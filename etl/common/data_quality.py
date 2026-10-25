"""
Data Quality Validation Functions
Functions for checking data quality across Bronze/Silver/Gold layers
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, count, countDistinct, isnan, isnull, when


class DataQualityChecker:
    """Data quality validation utility"""
    
    def __init__(self, spark):
        self.spark = spark
        self.results = []
    
    def check_row_count(self, df, table_name, expected_count=None, tolerance=0.0):
        """
        Check row count against expected value
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
            expected_count: Expected row count (optional)
            tolerance: Allowed percentage difference (0.0 = exact match)
        
        Returns:
            dict: Check result
        """
        actual_count = df.count()
        
        result = {
            "check": "row_count",
            "table": table_name,
            "actual": actual_count,
            "expected": expected_count,
            "status": "PASS"
        }
        
        if expected_count is not None:
            diff_pct = abs(actual_count - expected_count) / expected_count if expected_count > 0 else 0
            if diff_pct > tolerance:
                result["status"] = "FAIL"
                result["message"] = f"Row count mismatch: {actual_count} vs {expected_count} (diff: {diff_pct*100:.2f}%)"
        
        self.results.append(result)
        return result
    
    def check_nulls(self, df, table_name, columns, tolerance=0.0):
        """
        Check for null values in specified columns
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
            columns: List of column names to check
            tolerance: Maximum allowed null percentage (0.0 = no nulls allowed)
        
        Returns:
            dict: Check result
        """
        total_rows = df.count()
        
        for column in columns:
            null_count = df.filter(col(column).isNull()).count()
            null_pct = null_count / total_rows if total_rows > 0 else 0
            
            result = {
                "check": "nulls",
                "table": table_name,
                "column": column,
                "null_count": null_count,
                "null_percentage": null_pct * 100,
                "total_rows": total_rows,
                "status": "PASS" if null_pct <= tolerance else "FAIL"
            }
            
            if null_pct > tolerance:
                result["message"] = f"Null percentage {null_pct*100:.2f}% exceeds tolerance {tolerance*100:.2f}%"
            
            self.results.append(result)
    
    def check_uniqueness(self, df, table_name, column):
        """
        Check if column values are unique (no duplicates)
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
            column: Column name to check for uniqueness
        
        Returns:
            dict: Check result
        """
        total_count = df.count()
        distinct_count = df.select(column).distinct().count()
        duplicate_count = total_count - distinct_count
        
        result = {
            "check": "uniqueness",
            "table": table_name,
            "column": column,
            "total_rows": total_count,
            "distinct_values": distinct_count,
            "duplicates": duplicate_count,
            "status": "PASS" if duplicate_count == 0 else "FAIL"
        }
        
        if duplicate_count > 0:
            result["message"] = f"Found {duplicate_count} duplicate values in {column}"
        
        self.results.append(result)
        return result
    
    def check_referential_integrity(self, child_df, parent_df, child_col, parent_col, 
                                   child_table, parent_table):
        """
        Check referential integrity - all child keys exist in parent
        
        Args:
            child_df: Child DataFrame
            parent_df: Parent DataFrame
            child_col: Foreign key column in child table
            parent_col: Primary key column in parent table
            child_table: Name of child table
            parent_table: Name of parent table
        
        Returns:
            dict: Check result
        """
        # Find orphaned records (child keys not in parent)
        orphaned = child_df.join(
            parent_df,
            child_df[child_col] == parent_df[parent_col],
            "left_anti"
        )
        orphaned_count = orphaned.count()
        
        result = {
            "check": "referential_integrity",
            "child_table": child_table,
            "parent_table": parent_table,
            "foreign_key": child_col,
            "primary_key": parent_col,
            "orphaned_records": orphaned_count,
            "status": "PASS" if orphaned_count == 0 else "FAIL"
        }
        
        if orphaned_count > 0:
            result["message"] = f"Found {orphaned_count} orphaned records in {child_table}.{child_col}"
        
        self.results.append(result)
        return result
    
    def check_value_range(self, df, table_name, column, min_val=None, max_val=None):
        """
        Check if values are within expected range
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
            column: Column name to check
            min_val: Minimum allowed value
            max_val: Maximum allowed value
        
        Returns:
            dict: Check result
        """
        out_of_range_count = 0
        
        if min_val is not None and max_val is not None:
            out_of_range_count = df.filter(
                (col(column) < min_val) | (col(column) > max_val)
            ).count()
        elif min_val is not None:
            out_of_range_count = df.filter(col(column) < min_val).count()
        elif max_val is not None:
            out_of_range_count = df.filter(col(column) > max_val).count()
        
        result = {
            "check": "value_range",
            "table": table_name,
            "column": column,
            "min_value": min_val,
            "max_value": max_val,
            "out_of_range_count": out_of_range_count,
            "status": "PASS" if out_of_range_count == 0 else "FAIL"
        }
        
        if out_of_range_count > 0:
            result["message"] = f"Found {out_of_range_count} values outside range [{min_val}, {max_val}]"
        
        self.results.append(result)
        return result
    
    def get_summary(self):
        """Get summary of all checks"""
        total = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = total - passed
        
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "details": self.results
        }
    
    def print_summary(self):
        """Print formatted summary to console"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("DATA QUALITY CHECK SUMMARY")
        print("="*60)
        print(f"Total Checks: {summary['total_checks']}")
        print(f"Passed:       {summary['passed']}")
        print(f"Failed:       {summary['failed']}")
        print(f"Pass Rate:    {summary['pass_rate']:.1f}%")
        print("="*60)
        
        # Print failed checks
        if summary['failed'] > 0:
            print("\nFAILED CHECKS:")
            for result in self.results:
                if result["status"] == "FAIL":
                    print(f"  ✗ {result['check']} - {result.get('table', '')} - {result.get('message', 'Failed')}")
        
        print("\n")
