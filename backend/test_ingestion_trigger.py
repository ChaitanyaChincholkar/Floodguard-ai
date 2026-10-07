from app.ingestion.tasks import ingest_rainfall_data

print("Triggering rainfall ingestion task...")
ingest_rainfall_data.delay()
print("Task triggered successfully!")
