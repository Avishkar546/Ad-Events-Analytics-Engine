from unittest.mock import MagicMock, patch

from app.services.aggregation_service import AggregationRunSummary


@patch("app.workers.run_once.run_aggregation_job")
@patch("app.workers.run_once.get_client")
def test_main_runs_aggregation_job_once(mock_get_client, mock_run_job):
    mock_run_job.return_value = AggregationRunSummary(advertisers_processed=2, advertiser_ids=[1, 2])
    mock_get_client.return_value = MagicMock()

    from app.workers.run_once import main

    main()

    mock_get_client.assert_called_once()
    mock_run_job.assert_called_once_with(mock_get_client.return_value)
