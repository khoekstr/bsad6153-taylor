-- Reader-only report. Preview/no-op runs do not claim a fresh source check.
WITH recent AS (
 SELECT * FROM sync_runs WHERE started_at >= now() - interval '7 days'
), totals AS (
 SELECT count(*) AS total_runs,
        count(*) FILTER (WHERE dry_run) AS preview_runs,
        count(*) FILTER (WHERE NOT dry_run AND status='success') AS successful_live_runs,
        count(*) FILTER (WHERE status='failed') AS failed_or_unfinished_runs,
        count(*) FILTER (WHERE status='partial') AS partial_runs,
        coalesce(sum(records_inserted) FILTER (WHERE NOT dry_run AND finished_at IS NOT NULL),0) AS works_added,
        coalesce(sum(records_updated) FILTER (WHERE NOT dry_run AND finished_at IS NOT NULL),0) AS works_updated
 FROM recent
)
SELECT jsonb_build_object(
 'as_of', now(),
 'last_successful_discovery_at', (SELECT max(finished_at) FROM sync_runs
   WHERE NOT dry_run AND status='success' AND mode='discovery_only' AND outcome='completed'),
 'last_committed_work_change_at', (SELECT max(finished_at) FROM sync_runs
   WHERE NOT dry_run AND status IN ('success','partial') AND records_inserted+records_updated>0),
 'last_7_days', (SELECT to_jsonb(totals) FROM totals),
 'recent_runs', coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.started_at DESC) FROM
   (SELECT run_id,started_at,finished_at,status,trigger,dry_run,mode,outcome,
           records_fetched,records_inserted,records_updated,error_message,details
    FROM recent ORDER BY started_at DESC LIMIT 20) r),'[]'::jsonb)
);
