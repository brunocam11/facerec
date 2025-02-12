# Scaling Strategy

## Instance Requirements & Concurrency

### Base Configuration
```yaml
Instance Type: c6i.2xlarge
Specs:
  - 8 vCPUs
  - 16GB RAM
  - Processing Speed: ~20 images/second
  - Cost: ~$250/month

Processing Capacity:
  - Single Album (5000 images): ~4-5 minutes
  - Daily Capacity: ~350,000 images
```

### Concurrent Album Processing
Given:
- Average album size: 3000-5000 images
- Processing time: ~4-5 minutes per album
- Peak periods: Multiple uploads likely

Auto-scaling Strategy:
```yaml
ECS Service Configuration:
  Minimum: 1 instance
  Desired: 1-2 instances
  Maximum: 4 instances

Scale-up Triggers:
  - SQS Queue Length > 1 album (3000+ images)
  - CPU Utilization > 70%
  - Processing Time > 6 minutes

Scale-down Triggers:
  - Queue Empty for 10 minutes
  - CPU Utilization < 30%
```

### Concurrent Upload Scenario
Example: 3 albums uploaded within 5 minutes
```plaintext
Album A: 5000 images
Album B: 4000 images
Album C: 3000 images

Auto-scaling Response:
1. First instance starts processing Album A
2. Queue length triggers scale-up
3. Second instance starts Album B
4. Third instance starts Album C if needed

Maximum Wait Time: < 2 minutes for processing start
Total Processing Time: ~6-7 minutes
```

### Search Service
The same instances handle search requests:
- Face search: < 500ms per request
- Concurrent searches: 50+ per instance
- Search traffic doesn't impact processing significantly 