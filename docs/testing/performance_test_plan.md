# Performance Testing Plan

## Phase 1: Single Instance Testing

### Test Setup
```yaml
Instance: c6i.2xlarge
Test Data:
  - Small Album: 1000 images
  - Medium Album: 3000 images
  - Large Album: 5000 images
```

### Tests to Run
1. **Basic Processing Speed**
   - Process single album
   - Measure time per image
   - Monitor CPU/Memory usage

2. **Concurrent Operations**
   - Process album while handling search requests
   - Measure impact on processing speed
   - Measure search response times

3. **Resource Usage**
   - Monitor memory with model loaded
   - Track CPU usage patterns
   - Measure network I/O

## Phase 2: Load Testing

1. **Multiple Album Upload**
   - Upload 2-3 albums concurrently
   - Monitor processing times
   - Check for failures

2. **Search Under Load**
   - Run searches while processing albums
   - Measure response times
   - Check for timeouts

## Test Metrics to Collect
- Processing time per image
- Memory usage patterns
- CPU utilization
- Search response times
- Failure rates 