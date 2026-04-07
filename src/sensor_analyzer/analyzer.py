"""
Module containing the logic for processing and analyzing sensor data.

This module provides the SensorAnalyzer class, which is responsible for:
- Loading CSV files with sensor data.
- Filtering files by date.
- Calculating the median measurement time.
- Categorizing results (success, failure, alarm) based on requirements.
- Generating a flattened result matrix ready for export.
"""

import itertools
from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd


class SensorAnalyzer:
    """
    Class responsible for analyzing measurement data from CSV files.

    Loads files, calculates the median duration of measurements for all
    sensors, and generates a matrix summarizing the results.
    """

    def __init__(self, data_dir: str = "sample_data"):
        """
        Initializes the sensor analyzer.

        Args:
            data_dir (str): Path to the directory containing CSV data files.
                            Defaults to 'sample_data'.

        Raises:
            FileNotFoundError: If the directory does not exist.
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
        if not self.data_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {data_dir}")

    def _parse_date(self, date_str: str) -> datetime:
        """
        Converts a string to a datetime object.

        Args:
            date_str (str): Date in 'DD.MM.YYYY' format.

        Returns:
            datetime: Date object.

        Raises:
            ValueError: If the date format is invalid.
        """
        return datetime.strptime(date_str, "%d.%m.%Y")

    def get_files_in_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Path]:
        """
        Retrieves and sorts a list of CSV files within a given date range.

        Args:
            start_date (datetime): Start date object.
            end_date (datetime): End date object.

        Returns:
            list[Path]: Chronologically sorted list of file paths.
        """
        files: list[Path] = []
        for csv_file in self.data_dir.glob("*.csv"):
            try:
                file_date = self._parse_date(csv_file.stem)
                if start_date <= file_date <= end_date:
                    files.append(csv_file)
            except ValueError:
                continue

        return sorted(files, key=lambda f: self._parse_date(f.stem))

    def process_data(self, files: list[Path]) -> pd.DataFrame:
        """
        Processes data from a list of files and generates a result matrix.
        """
        if not files:
            return pd.DataFrame()

        # 1. Load data
        data_by_date, all_sensors = self._load_measurements(files)

        # 2. Prepare sorted list of sensors
        sorted_sensors = sorted(list(all_sensors), key=lambda x: (len(x), x))

        # 3. Build result matrix
        result_matrix = {"Sensor": sorted_sensors}  # first column

        for date_str, df in data_by_date.items():
            # Calculate success threshold for the day
            threshold = self._calculate_threshold(df)
            
            # Index once for the day to speed up lookup
            day_df_indexed = df.set_index("name")
            daily_results = [
                self._determine_status(sensor, day_df_indexed, threshold)
                for sensor in sorted_sensors
            ]
            result_matrix[date_str] = daily_results

        return pd.DataFrame(result_matrix)

    def _load_measurements(
        self, files: list[Path]
    ) -> tuple[dict[str, pd.DataFrame], set[str]]:
        """Loads data from CSV files and standardizes column names."""
        data_by_date = {}
        all_sensors = set()

        for file_path in files:
            df = pd.read_csv(file_path)
            df.columns = ["name", "description", "time", "alarm"]
            data_by_date[file_path.stem] = df
            all_sensors.update(df["name"].unique())

        return data_by_date, all_sensors

    def _calculate_threshold(self, df: pd.DataFrame) -> float:
        """Calculates the success threshold (0.5 * median) for data from one day."""
        if df.empty or "time" not in df.columns:
            return 0.0
        return cast(float, df["time"].median() / 2)

    def _determine_status(
        self, sensor_name: str, day_df_indexed: pd.DataFrame, threshold: float
    ) -> str:
        """Determines the status symbol for a single measurement based on threshold and alarm."""
        if sensor_name not in day_df_indexed.index:
            return "-"

        sensor_row = day_df_indexed.loc[sensor_name]
        # Handle potential duplicates in the index
        if isinstance(sensor_row, pd.DataFrame):
            sensor_row = sensor_row.iloc[0]

        try:
            raw_time = float(sensor_row["time"])
        except (ValueError, TypeError):
            return "-"

        if raw_time < threshold:
            return "-"

        raw_alarm = str(sensor_row["alarm"]).strip().lower()
        has_alarm = raw_alarm in ["yes", "true", "1"]
        return "!" if has_alarm else "+"
