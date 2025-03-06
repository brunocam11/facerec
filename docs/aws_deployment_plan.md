# Deployment Plan for Facial Recognition Service on AWS EC2 Spot Fleet

## Phase 1: Architecture Setup and Base Infrastructure

### Step 1: Create SQS Queues
```
1. Create main queue for indexing tasks
   - Set visibility timeout to 5 minutes initially (adjustable based on processing time)
   - Enable message retention (4-14 days)
   - Set maximum receives before moving to DLQ (e.g., 5)
   
2. Create Dead Letter Queue (DLQ)
   - Configure appropriate alerting
```

### Step 2: Refactor Existing Application
```
1. Separate the indexing logic from API endpoints
   - Extract core indexing functionality to a reusable service
   - Ensure both API and worker can use same underlying service
   
2. Create SQS message producer for indexing API
   - Modify index_faces API to enqueue tasks instead of processing directly
   - Preserve API interface to maintain compatibility
```

### Step 3: Create Worker Service
```
1. Develop SQS consumer worker
   - Implement multiprocessing pool to process messages in parallel
   - Use optimal batch size (10-20 images per batch)
   - Handle graceful shutdowns for spot interruptions
   - Implement proper message acknowledgment

2. Create container image for worker
   - Package with Docker
   - Optimize for ML workloads
```

## Phase 2: AWS Infrastructure and Deployment

### Step 4: Set Up EC2 Spot Fleet and ASG
```
1. Create Launch Template
   - Select appropriate instance types optimized for ML (e.g., c5/c6/g4dn)
   - Configure user data for worker initialization
   - Set up IAM roles with proper permissions

2. Create Auto Scaling Group
   - Configure spot fleet request with diverse instance types
   - Set up scaling policies based on SQS queue depth
   - Configure instance protection during processing
```

### Step 5: Configure CloudWatch Monitoring
```
1. Set up metrics and alarms
   - Queue depth monitoring
   - Processing success/failure rates
   - Instance health and availability
   - DLQ monitoring

2. Create dashboard for service metrics
```

### Step 6: Update API Service Deployment
```
1. Deploy updated API service
   - Configure to use SQS for indexing
   - Keep direct processing for face matching
   - Set up appropriate scaling for API tier
```

## Phase 3: Testing and Optimization

### Step 7: Create Test Harness
```python
# Example pseudocode for test script
def load_testing_script():
    """
    - Connect to S3
    - Configure batch sizes and total image count
    - For each album, push messages to SQS in batches
    - Monitor processing rate and success
    """
```

### Step 8: Progressive Load Testing
```
1. Initial test with 1,000 images
   - Validate end-to-end processing
   - Measure processing time and resource utilization
   
2. Medium scale test (10,000 images)
   - Test auto-scaling capabilities
   - Identify bottlenecks
   
3. Large scale test (50,000+ images)
   - Validate performance at scale
   - Test recovery from instance interruptions
```

### Step 9: Optimization
```
1. Tune parameters based on test results
   - Adjust batch sizes
   - Optimize instance types and distribution
   - Fine-tune auto-scaling parameters
   - Adjust visibility timeouts
```

## Detailed Implementation Notes

### Worker Implementation Considerations

1. **Stateless Processing**:
   ```python
   # Pseudocode for stateless worker
   def process_messages(batch_size=10):
       while not shutdown_flag:
           messages = sqs.receive_messages(MaxNumberOfMessages=batch_size, WaitTimeSeconds=20)
           if messages:
               with concurrent.futures.ProcessPoolExecutor(max_workers=cpu_count()) as executor:
                   futures = [executor.submit(process_single_image, message) for message in messages]
                   for future, message in zip(futures, messages):
                       try:
                           result = future.result(timeout=timeout)
                           message.delete()  # Acknowledge on success
                       except Exception as e:
                           # Log error, message will return to queue after visibility timeout
                           logger.error(f"Processing failed: {e}")
   ```

2. **Graceful Shutdown Handler**:
   ```python
   # Pseudocode for handling spot termination
   def setup_termination_handler():
       def handler(signum, frame):
           nonlocal shutdown_flag
           shutdown_flag = True
           logger.info("Received termination signal, shutting down gracefully")
       
       signal.signal(signal.SIGTERM, handler)
   ```

3. **SQS Message Format**:
   ```json
   {
     "image_id": "album123/image456.jpg",
     "collection_id": "user_album_123",
     "s3_bucket": "spotted-images-protected",
     "s3_key": "album123/image456.jpg",
     "max_faces": 5
   }
   ```

### API Modification for Queuing

```python
# Example modification to index_faces endpoint
@router.post("/faces/index", response_model=IndexJobResponse)
async def index_faces(
    image: UploadFile = File(...),
    collection_id: str = Form(...),
    image_id: str = Form(...),
    max_faces: Optional[int] = Form(5),
    sqs_service: SQSService = Depends(get_sqs_service),
) -> IndexJobResponse:
    # Save image to S3 if not already there
    s3_key = f"{collection_id}/{image_id}"
    s3_service.upload_fileobj(image.file, s3_key)
    
    # Enqueue indexing job
    message_body = {
        "image_id": image_id,
        "collection_id": collection_id,
        "s3_bucket": settings.AWS_S3_BUCKET,
        "s3_key": s3_key,
        "max_faces": max_faces
    }
    job_id = sqs_service.send_message(message_body)
    
    return {"job_id": job_id, "status": "SUBMITTED"}
```

## Next Steps and Timeline

1. **Week 1**: SQS queue setup and application refactoring
2. **Week 2**: Worker implementation and testing
3. **Week 3**: EC2 Spot Fleet and ASG configuration
4. **Week 4**: End-to-end testing and initial load testing
5. **Week 5**: Progressive load testing and optimization 