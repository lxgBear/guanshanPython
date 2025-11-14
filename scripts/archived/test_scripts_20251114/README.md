# 归档测试脚本

**归档日期**: 2025-11-14
**原因**: 功能验证完成，已不再需要

## 说明

这些脚本完成了特定功能的测试验证，归档保留以供参考。

## 恢复方法

如需使用这些脚本:

```bash
cp scripts/archived/test_scripts_20251114/<script_name> scripts/
```

## 内容列表

-rw-r--r--  1 lanxionggao  staff   5.9K 11  6 12:38 scripts/archived/test_scripts_20251114/analyze_duplicate_key_issue.py
-rw-r--r--  1 lanxionggao  staff   6.2K 11  6 18:06 scripts/archived/test_scripts_20251114/analyze_saved_results.py
-rw-r--r--  1 lanxionggao  staff   2.2K 11  5 17:31 scripts/archived/test_scripts_20251114/check_crawl_urls.py
-rw-r--r--  1 lanxionggao  staff   1.8K 11  5 17:32 scripts/archived/test_scripts_20251114/check_detailed_metadata.py
-rw-r--r--  1 lanxionggao  staff   5.4K 11  6 11:27 scripts/archived/test_scripts_20251114/check_failed_smart_search_task.py
-rw-r--r--  1 lanxionggao  staff   6.6K 11  5 23:03 scripts/archived/test_scripts_20251114/check_firecrawl_raw_data.py
-rw-r--r--  1 lanxionggao  staff   6.0K 11  5 22:56 scripts/archived/test_scripts_20251114/check_markdown_content.py
-rw-r--r--  1 lanxionggao  staff   3.4K 11  5 23:40 scripts/archived/test_scripts_20251114/check_media_urls_samples.py
-rw-r--r--  1 lanxionggao  staff   1.6K 11  5 17:47 scripts/archived/test_scripts_20251114/check_news_results_issue.py
-rw-r--r--  1 lanxionggao  staff   8.4K 11  5 23:39 scripts/archived/test_scripts_20251114/check_news_results_nested_fields.py
-rw-r--r--  1 lanxionggao  staff   1.9K 10 31 17:09 scripts/archived/test_scripts_20251114/check_old_status.py
-rw-r--r--  1 lanxionggao  staff   1.4K 11  3 17:21 scripts/archived/test_scripts_20251114/check_smart_search_data.py
-rw-r--r--  1 lanxionggao  staff   5.2K 11  5 15:56 scripts/archived/test_scripts_20251114/check_task_status.py
-rw-r--r--  1 lanxionggao  staff   3.1K 11  5 22:33 scripts/archived/test_scripts_20251114/check_test_tasks.py
-rw-r--r--  1 lanxionggao  staff    16K 11  4 14:52 scripts/archived/test_scripts_20251114/test_api_v201_real.py
-rw-r--r--  1 lanxionggao  staff    16K 11  4 11:59 scripts/archived/test_scripts_20251114/test_api_v201.py
-rw-r--r--  1 lanxionggao  staff   7.1K 11  4 16:39 scripts/archived/test_scripts_20251114/test_content_removal.py
-rw-r--r--  1 lanxionggao  staff    13K 10 16 13:55 scripts/archived/test_scripts_20251114/test_crawl_mode_complete.py
-rw-r--r--  1 lanxionggao  staff    14K 10 24 11:35 scripts/archived/test_scripts_20251114/test_data_source_curation_simple.py
-rw-r--r--  1 lanxionggao  staff    17K 10 23 19:06 scripts/archived/test_scripts_20251114/test_data_source_curation.py
-rwxr-xr-x  1 lanxionggao  staff    12K 10 17 16:45 scripts/archived/test_scripts_20251114/test_db_and_firecrawl.py
-rw-r--r--  1 lanxionggao  staff   8.6K 11  5 23:16 scripts/archived/test_scripts_20251114/test_exclude_tags_fix.py
-rw-r--r--  1 lanxionggao  staff   4.5K 11  6 11:37 scripts/archived/test_scripts_20251114/test_fixed_smart_search.py
-rw-r--r--  1 lanxionggao  staff   5.9K 10 14 17:00 scripts/archived/test_scripts_20251114/test_gnlm_crawl.py
-rw-r--r--  1 lanxionggao  staff   5.5K 11  4 15:22 scripts/archived/test_scripts_20251114/test_immediate_execution.py
-rw-r--r--  1 lanxionggao  staff   4.5K 10 21 15:31 scripts/archived/test_scripts_20251114/test_instant_search_5_results.py
-rw-r--r--  1 lanxionggao  staff    10K 10 16 12:02 scripts/archived/test_scripts_20251114/test_instant_search_api.py
-rw-r--r--  1 lanxionggao  staff   8.2K 10 21 15:04 scripts/archived/test_scripts_20251114/test_instant_search_task.py
-rwxr-xr-x  1 lanxionggao  staff   2.1K 10 23 14:48 scripts/archived/test_scripts_20251114/test_instant_search_timeout_fix.py
-rw-r--r--  1 lanxionggao  staff   4.0K 10 23 14:48 scripts/archived/test_scripts_20251114/test_language_filter.py
-rw-r--r--  1 lanxionggao  staff   3.4K 11  6 23:04 scripts/archived/test_scripts_20251114/test_map_api.py
-rw-r--r--  1 lanxionggao  staff    10K 11  6 23:26 scripts/archived/test_scripts_20251114/test_map_scrape_integration.py
-rw-r--r--  1 lanxionggao  staff   9.6K 11  5 22:27 scripts/archived/test_scripts_20251114/test_metadata_field_extraction.py
-rw-r--r--  1 lanxionggao  staff    11K 11  4 12:04 scripts/archived/test_scripts_20251114/test_processed_result_field_copy.py
-rwxr-xr-x  1 lanxionggao  staff    11K 10 21 12:59 scripts/archived/test_scripts_20251114/test_production_database.py
-rw-r--r--  1 lanxionggao  staff   3.4K 10 31 15:31 scripts/archived/test_scripts_20251114/test_snowflake_id_system.py
-rw-r--r--  1 lanxionggao  staff   2.2K 11  5 17:35 scripts/archived/test_scripts_20251114/test_status_fix.py
-rw-r--r--  1 lanxionggao  staff    21K 10 20 18:35 scripts/archived/test_scripts_20251114/test_summary_report_api.py
-rw-r--r--  1 lanxionggao  staff    15K 10 23 15:43 scripts/archived/test_scripts_20251114/test_summary_report_v2_cleanup.py
-rwxr-xr-x  1 lanxionggao  staff    10K 11  3 21:42 scripts/archived/test_scripts_20251114/test_unified_architecture.py
-rw-r--r--  1 lanxionggao  staff    11K 11  7 00:28 scripts/archived/test_scripts_20251114/test_url_filtering.py
-rw-r--r--  1 lanxionggao  staff   5.2K 10 20 11:53 scripts/archived/test_scripts_20251114/test_vpn_api.py
-rwxr-xr-x  1 lanxionggao  staff   8.5K 10 20 20:28 scripts/archived/test_scripts_20251114/test_vpn_database.py
-rw-r--r--  1 lanxionggao  staff   8.0K 11  5 23:48 scripts/archived/test_scripts_20251114/validate_v203_entity_updates.py
-rwxr-xr-x  1 lanxionggao  staff   5.2K 10 10 17:20 scripts/archived/test_scripts_20251114/validate.py
-rw-r--r--  1 lanxionggao  staff   7.2K 11  7 00:07 scripts/archived/test_scripts_20251114/verify_map_scrape_api.py
-rw-r--r--  1 lanxionggao  staff   8.9K 11  5 22:47 scripts/archived/test_scripts_20251114/verify_metadata_optimization.py
